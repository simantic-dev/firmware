"""ADBMS6830B daisy chain (10 ICs) as one scripted SPI peer for the FEB SN5 BMS.

Firmware: FEB_FIRMWARE_SN5/BMS. The chain size is FEB_NUM_IC = FEB_NUM_ICPBANK (1)
* FEB_NBANKS (10) in Core/User/Inc/FEB_Const.h. The MCU drives SPI1 with CS on PC3
  (FEB_HW.h / main.h), so the peer sits on spi1 behind cs PC3.

Wire framing, as the firmware's FEB_AD68xx_Interface.c and FEB_ADBMS6830B_Driver.c use it:
  - command: 2 bytes + PEC15 (2 bytes, big endian)
  - write (WRCFGA/WRCFGB): then for the chain, last IC first: 6 data bytes + PEC10 (2 bytes)
  - read: 8 bytes per IC, IC 0 first: 6 data bytes, then {CC[5:0], PEC10[9:8]}, PEC10[7:0]
  - a transaction of one 0xFF byte is wakeup_idle(): ignored
  - the chip's 6-bit command counter (CC) advances on valid write and action commands,
    and not on reads (same rule as ADBMS_CC_Advance in the firmware)

Commands the firmware sends (grep of Core/User/Src):
  init:     WRCFGA 0x0001, WRCFGB 0x0024, RDCFGA 0x0002, RDCFGB 0x0026, RDSID 0x002C
  per scan: ADCV (action, 0x03xx), ADSV 0x01E0 (action), ADAX (action, 0x05xx/0x04xx),
            RDCVA-F 0x0004/06/08/0A/09/0B, RDSVA-F 0x0003/05/07/0D/0E/0F,
            RDAUXA 0x0019, RDAUXB 0x001A
  Any other valid 2-byte command is treated as an action (it advances the CC, returns nothing).

Run (single machine, the peer as a board part):
  sim STM32F446RE run --elf BMS.elf --board <board file naming this script> --timeout 3 -q

Self-check: python3 adbms6830b.py   (PEC vectors from the firmware's own pec15_calc and
Pec10_calc, compiled from FEB_AD68xx_Interface.c on a host.)
"""

import math

N_IC = 10  # FEB_NUM_IC, see above

# Profile (use case: BMS on the car). MODELED SIMPLIFICATION: time-compressed, one virtual
# second stands for minutes of pack time, so a 10 s run shows a full rest/load/fault cycle.
LOAD_START_S = 2.0   # MODELED SIMPLIFICATION: load step at 2 s
LOAD_END_S = 8.0     # MODELED SIMPLIFICATION: load released at 8 s, no RC relaxation after
LOAD_A = 60.0        # MODELED SIMPLIFICATION: pack current, flows through every cell in series
CELL_R_OHM = 0.003   # MODELED SIMPLIFICATION: per-cell internal resistance; sag = I * R
SOC0 = 0.75          # MODELED SIMPLIFICATION: starting state of charge
SOC_PER_AS = 0.05 / 360.0  # MODELED SIMPLIFICATION: 5 % SOC over the 360 A s load
OCV_V_PER_SOC = 0.8  # MODELED SIMPLIFICATION: linear OCV slope, 0.8 V per unit SOC
CELL_V_REST = 3.70   # rest voltage per cell (task profile: about 3.7 V)
# MODELED SIMPLIFICATION: thermal model. Ambient and the heating shape are invented.
T_AMB_C = 25.0
T_LOAD_RISE_C = 4.0  # pack-wide heating over the load
HOT_BANK = 4         # IC 4 carries a hot cell; all its sensors read hot (one bank = one IC)
T_HOT_RISE_C = 33.0  # extra heating on HOT_BANK
HOT_RAMP_S = 5.0     # ramp length for the hot bank

# Thermistor network, FEB_Const.h THERM_*: Vs 5 V, 10k pull-up, 10k NTC at 25 C, B = 3428.
NTC_R25_OHM = 10000.0
NTC_B = 3428.0
NTC_PULLUP_OHM = 10000.0
NTC_VS_V = 5.0


def _code(volts):
    # Firmware convert_voltage(): V = code * 150 uV + 1.5 V (ADBMS_ADC_LSB_V / OFFSET_V).
    return int(round((volts - 1.5) / 0.000150))


def _u16(code):
    # The firmware reads codes as int16_t, so a voltage below 1.5 V is a negative code.
    return code & 0xFFFF


def _clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def cell_voltage(t):
    """Cell voltage in volts at virtual time t (seconds)."""
    dis_as = LOAD_A * min(max(t - LOAD_START_S, 0.0), LOAD_END_S - LOAD_START_S)
    soc = SOC0 - SOC_PER_AS * dis_as
    ocv = CELL_V_REST + OCV_V_PER_SOC * (soc - SOC0)
    load = LOAD_A if LOAD_START_S <= t < LOAD_END_S else 0.0
    return ocv - load * CELL_R_OHM


def bank_temp_c(bank, t):
    """Temperature in degC of IC `bank`'s thermistors at virtual time t (seconds)."""
    frac = _clamp01((t - LOAD_START_S) / (LOAD_END_S - LOAD_START_S))
    temp = T_AMB_C + T_LOAD_RISE_C * frac
    if bank == HOT_BANK:
        temp += T_HOT_RISE_C * _clamp01((t - LOAD_START_S) / HOT_RAMP_S)
    return temp


def ntc_volts(temp_c):
    """Divider voltage for the NTC at temp_c: Vs * R / (R + Rpullup)."""
    tk = temp_c + 273.15
    r = NTC_R25_OHM * math.exp(NTC_B * (1.0 / tk - 1.0 / 298.15))
    return NTC_VS_V * r / (r + NTC_PULLUP_OHM)

READS = {
    0x0002: ("cfga",),
    0x0026: ("cfgb",),
    0x0004: ("cv", 0), 0x0006: ("cv", 1), 0x0008: ("cv", 2),
    0x000A: ("cv", 3), 0x0009: ("cv", 4), 0x000B: ("cv", 5),
    0x0003: ("sv", 0), 0x0005: ("sv", 1), 0x0007: ("sv", 2),
    0x000D: ("sv", 3), 0x000E: ("sv", 4), 0x000F: ("sv", 5),
    0x0019: ("aux", 0), 0x001A: ("aux", 1),
    0x002C: ("sid",),
}
WRITES = {0x0001: "cfga", 0x0024: "cfgb"}


def pec15(data):
    """PEC15 over bytes, as pec15_calc(): remainder seed 16, poly 0x4599, result * 2."""
    rem = 16
    for byte in data:
        for bit in range(7, -1, -1):
            top = ((rem >> 14) & 1) ^ ((byte >> bit) & 1)
            rem = (rem << 1) & 0x7FFF
            if top:
                rem ^= 0x4599
    return (rem << 1) & 0xFFFF


def pec10(data, cc_byte=None):
    """PEC10 as Pec10_calc(): seed 16, poly 0x8F, 6 trailing steps.

    cc_byte: the received byte 6 (CC << 2 | PEC hi) for an RX PEC; None for a TX PEC.
    """
    rem = 16
    for byte in data:
        rem ^= byte << 2
        for _ in range(8):
            rem = ((rem << 1) ^ (0x8F if rem & 0x200 else 0)) & 0xFFFF
    if cc_byte is not None:
        rem ^= (cc_byte & 0xFC) << 2
    for _ in range(6):
        rem = ((rem << 1) ^ (0x8F if rem & 0x200 else 0)) & 0xFFFF
    return rem & 0x3FF


def _frame(data, cc):
    """One IC's 8 bytes on a read: data, {CC, PEC[9:8]}, PEC[7:0]."""
    byte6 = (cc & 0x3F) << 2
    pec = pec10(data, byte6)
    return bytes(data) + bytes([byte6 | (pec >> 8), pec & 0xFF])


class Slave:
    def __init__(self, ctx):
        self.ctx = ctx
        self.cc = 0
        self.cfga = [bytes([0x03, 0x00, 0x00, 0xFF, 0x03, 0x00])] * N_IC
        self.cfgb = [bytes([0x00, 0x00, 0x00, 0xFF, 0x00, 0x00])] * N_IC
        self.sid = [bytes([0xB6, 0x83, 0x00, 0x00, 0x00, i + 1]) for i in range(N_IC)]
        self.mosi = bytearray()
        self.miso = b""

    def on_transmit(self, b):
        i = len(self.mosi)
        self.mosi.append(b)
        if i == 3:
            self.miso = self._respond()
        if i < 4:
            return 0x00
        k = i - 4
        return self.miso[k] if k < len(self.miso) else 0x00

    def on_finish(self):
        txn = bytes(self.mosi)
        self.mosi = bytearray()
        self.miso = b""
        if len(txn) < 4 or pec15(txn[:2]) != (txn[2] << 8 | txn[3]):
            return  # wakeup pulse, or a command the chip rejects on PEC
        code = txn[0] << 8 | txn[1]
        if code in READS:
            return  # reads do not advance the command counter
        if code in WRITES:
            self._write(WRITES[code], txn[4:])
        self.cc = (self.cc + 1) & 0x3F

    def _respond(self):
        if len(self.mosi) < 4:
            return b""
        code = self.mosi[0] << 8 | self.mosi[1]
        if pec15(self.mosi[:2]) != (self.mosi[2] << 8 | self.mosi[3]):
            return b""
        if code not in READS:
            return b""
        what = READS[code]
        t = self.ctx.now_us / 1e6 if self.ctx is not None else 0.0
        cell = _u16(_code(cell_voltage(t)))
        frames = []
        for ic in range(N_IC):
            if what[0] == "cfga":
                data = self.cfga[ic]
            elif what[0] == "cfgb":
                data = self.cfgb[ic]
            elif what[0] == "sid":
                data = self.sid[ic]
            elif what[0] == "cv" or what[0] == "sv":
                data = bytes(c for _ in range(3) for c in cell.to_bytes(2, "little"))
            else:  # aux: IC index is the bank index (FEB_NUM_ICPBANK = 1)
                temp = _u16(_code(ntc_volts(bank_temp_c(ic, t))))
                data = b"".join(temp.to_bytes(2, "little") for _ in range(3))
            frames.append(_frame(data, self.cc))
        return b"".join(frames)

    def _write(self, name, payload):
        if len(payload) != 8 * N_IC:
            return
        target = self.cfga if name == "cfga" else self.cfgb
        # write_68 sends the chain last IC first: wire chunk k belongs to IC N_IC-1-k.
        for k in range(N_IC):
            chunk = payload[8 * k:8 * k + 8]
            data = chunk[:6]
            if (chunk[6] << 8 | chunk[7]) == pec10(data):
                target[N_IC - 1 - k] = bytes(data)  # echoed back on readback


def _selfcheck():
    # PEC15 vectors: firmware pec15_calc() compiled on the host.
    for cmd, want in [(0x0001, 0x3D6E), (0x0002, 0x2B0A), (0x0004, 0x07C2), (0x0006, 0x9A94),
                      (0x0008, 0x5E52), (0x000A, 0xC304), (0x0009, 0xD560), (0x000B, 0x4836),
                      (0x0003, 0xA038), (0x0005, 0x8CF0), (0x0007, 0x11A6), (0x000D, 0x64FE),
                      (0x000E, 0x729A), (0x000F, 0xF9A8), (0x0019, 0x8E4E), (0x001A, 0x982A),
                      (0x002C, 0x5990), (0x0024, 0xB19E), (0x0026, 0x2CC8), (0x0370, 0xAF42),
                      (0x0360, 0xF46C), (0x01E0, 0x2BE0), (0x0570, 0x888E), (0x0718, 0xAAFC),
                      (0x03F0, 0xEB64), (0x0380, 0xE19C)]:
        assert pec15(cmd.to_bytes(2, "big")) == want, hex(cmd)
    # PEC10 vectors: firmware Pec10_calc() on the same bytes.
    assert pec10([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]) == 0x1CC
    assert pec10([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC], 5 << 2) == 0x37F
    # Round trip: a config written as the firmware frames it reads back identically.
    s = Slave(None)
    payload = b"".join(bytes([0x11 * (ic + 1)] * 6) + pec10(bytes([0x11 * (ic + 1)] * 6)).to_bytes(2, "big")
                       for ic in reversed(range(N_IC)))
    s._write("cfga", payload)
    assert s.cfga[0] == bytes([0x11] * 6) and s.cfga[N_IC - 1] == bytes([0x11 * N_IC] * 6)
    assert _code(3.7) == 14667 and _code(2.5) == 6667
    assert abs(ntc_volts(25.0) - 2.5) < 1e-6  # the 25 C divider point
    assert _u16(_code(1.0)) == 0xF2FB  # below 1.5 V: negative int16 code, two's complement


if __name__ == "__main__":
    _selfcheck()
    print("adbms6830b selfcheck ok")
