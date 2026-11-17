"""TPS2482 power monitor, one instance per rail, on the FEB SN5 LVPDB I2C1 bus.

Firmware: FEB_FIRMWARE_SN5/LVPDB (Core/User/Src/FEB_Main.c), TPS library
common/FEB_TPS_Library (Src/feb_tps.c, Inc/feb_tps_registers.h).

Addresses (FEB_Main.h, FEB_TPS_ADDR): LV 0x4B, SH 0x4A, LT 0x40, BM_L 0x4F,
SM 0x42, AF1_AF2 0x41, CP_RF 0x47. Power-good lines are in lvpdb-peers.repl-frag.

Register behaviour follows the TPS2482 datasheet as the firmware uses it:
  CONFIG 0x00 (default 0x4127), SHUNT 0x01 (2.5 uV/LSB), BUS 0x02 (1.25 mV/LSB),
  CURRENT 0x04 = SHUNT * CAL / 2048, CAL 0x05, MASK 0x06 (OVF = bit 2), ALERT 0x07,
  ID 0xFF = 0x5449.
The CAL register is whatever the firmware writes, so the current register is
derived from it, not from a constant.

Identity: the bus routes an address only to the peer registered at it, so the
first on_address() call tells this instance which chip it is.
"""

R_SHUNT_OHM = 0.002  # WSR52L000FEA, the same shunt the firmware assumes (R_SHUNT)
# MODELED SIMPLIFICATION: power-good is asserted once the chip is addressed, i.e. the rail is up.
PG_HIGH_AT_ADDRESS = True

# MODELED SIMPLIFICATION: physical load profile per rail, invented. Each entry is
# (from_second, amps). lvpdb-dash.py turns AF1_AF2 and CP_RF on at 1.0 s, the same
# second these profiles step, so the firmware's EN edge should follow it.
# The 24 A step on AF1_AF2 at 6.0 s is the overcurrent event: the fuse rating used
# by the firmware for that rail is 20 A (AF1_AF2_FUSE_MAX, FEB_Main.h).
#   address: (name, bus volts, load profile)
PROFILE = {
    0x4B: ("LV", 24.0, [(0.0, 1.2)]),  # MODELED: 24 V housekeeping
    0x4A: ("SH", 24.0, [(0.0, 0.3)]),  # MODELED: shutdown circuit idle
    0x40: ("LT", 24.0, [(0.0, 1.5)]),  # MODELED: laptop branch idle
    0x4F: ("BM_L", 12.0, [(0.0, 0.8)]),  # MODELED: brake servo + lidar, 12 V rail
    0x42: ("SM", 24.0, [(0.0, 0.1)]),  # MODELED: steering motor, no assist
    0x41: ("AF1_AF2", 24.0, [(0.0, 0.0), (1.0, 9.0), (6.0, 24.0)]),  # MODELED: fans on, then overcurrent
    0x47: ("CP_RF", 24.0, [(0.0, 0.0), (1.0, 4.5)]),  # MODELED: coolant pump + radiator fans
}

REG_CONFIG, REG_SHUNT, REG_BUS, REG_CURRENT = 0x00, 0x01, 0x02, 0x04
REG_CAL, REG_MASK, REG_ALERT, REG_ID = 0x05, 0x06, 0x07, 0xFF
MASK_OVF = 1 << 2
CFG_RST = 1 << 15


def current_register(amps, cal):
    """Datasheet: CURRENT = SHUNT * CAL / 2048, SHUNT in 2.5 uV LSBs.

    Returns (register value, overflowed). The register is 15-bit magnitude here:
    past 0x7FFF it saturates and the math overflow flag is set.
    MODELED SIMPLIFICATION: the real part's value after OVF is not specified in this
    model; saturating at full scale is the stand-in.
    """
    shunt = int(round(amps * R_SHUNT_OHM / 2.5e-6))
    raw = (shunt * cal) // 2048
    if raw > 0x7FFF:
        return 0x7FFF, True
    return max(raw, 0), False


class Slave:
    def __init__(self, ctx):
        self.ctx = ctx
        self.addr = None
        self.name = "?"
        self.ptr = REG_CONFIG
        self.cursor = 0  # byte position inside the current read transaction (MSB first)
        self.regs = {REG_CONFIG: 0x4127, REG_CAL: 0, REG_MASK: 0, REG_ALERT: 0}

    def _amps(self):
        t = self.ctx.now_us / 1e6  # ctx.now_us is an attribute, not a method, on this bridge
        amps = 0.0
        for start, a in PROFILE[self.addr][2]:
            if t >= start:
                amps = a
        return amps

    def _read(self, reg):
        if reg == REG_BUS:
            return int(round(PROFILE[self.addr][1] / 0.00125))
        if reg == REG_SHUNT:
            return int(round(self._amps() * R_SHUNT_OHM / 2.5e-6))
        if reg == REG_CURRENT:
            cur, over = current_register(self._amps(), self.regs[REG_CAL])
            if over:
                self.regs[REG_MASK] |= MASK_OVF
            return cur
        if reg == REG_ID:
            return 0x5449
        return self.regs.get(reg, 0)

    def on_address(self, address, is_read):
        if self.addr is None:
            if address not in PROFILE:
                return False
            self.addr = address
            self.name = PROFILE[address][0]
            self.ctx.info(f"{self.name} addressed at 0x{address:02X}")
            if PG_HIGH_AT_ADDRESS:
                self.ctx.gpio(0).set(True)
        return address == self.addr

    def on_write(self, data):
        if not data:
            return
        self.ptr = data[0]
        self.cursor = 0
        if len(data) >= 3 and self.ptr != REG_CURRENT:
            value = (data[1] << 8) | data[2]
            if self.ptr == REG_CONFIG:
                value &= ~CFG_RST
            self.regs[self.ptr] = value
            self.ctx.info(f"{self.name} write reg 0x{self.ptr:02X} = 0x{value:04X}")

    def on_read(self, count):
        # The bridge may ask for the 2 bytes of one register in several calls; the chip
        # hands them out MSB first and keeps the cursor until the next write.
        value = self._read(self.ptr)
        data = bytes([(value >> 8) & 0xFF, value & 0xFF])[self.cursor:self.cursor + count]
        self.cursor += len(data)
        self.ctx.info(f"{self.name} read reg 0x{self.ptr:02X} -> 0x{value:04X}")
        return data.ljust(count, b"\x00")


if __name__ == "__main__":
    # Host self-check of the encoding, no sim needed. AF1_AF2 at 9 A with the CAL the
    # firmware computes for its 20 A range must read back as 9 A through its LSB.
    cal = int(0.00512 / ((20 / 32768) * R_SHUNT_OHM))
    reg, over = current_register(9.0, cal)
    assert not over and abs(reg * (20 / 32768) - 9.0) < 0.01, (cal, reg)
    assert current_register(24.0, cal) == (0x7FFF, True)
    print("ok", cal, reg)
