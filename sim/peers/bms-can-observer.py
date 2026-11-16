"""Passive CAN node on the SN5 BMS CAN1 bus: logs the BMS state and accumulator readings.

Firmware: FEB_FIRMWARE_SN5/BMS. Frames come from FEB_CAN_State.c, layouts from
common/FEB_CAN_Library_SN4/gen/FEB_CAN.dbc:
  id 0x02 bms_accumulator_voltage, sent every 100 ms: total_pack, min_cell, max_cell
          (raw = value x 10, so 0.1 V units; FEB_CAN_State.c packs V * 10)
  id 0x03 bms_accumulator_temperature, every 100 ms: avg, max, min (raw = degC x 10)
  id 0x05 bms_state, every 100 ms: bms_state bits 0-4, relay_state bits 8-10
The peer ACKs (any node on the bus does) and logs readings once a second, plus each
state change, so the readings and the fault entry are visible in the run output.

accumulator_faults (id 0x04) is in the DBC but the BMS never transmits it (no call
site in BMS/Core/User/Src), so it is not decoded here.
"""

FRAME_VOLTAGE = 0x02
FRAME_TEMP = 0x03
FRAME_BMS_STATE = 0x05
LOG_EVERY = 10  # frames at 100 ms cadence: one log line per second

BMS_STATE_NAMES = {  # FEB_CAN_State.h BMS_STATE_*
    0: "BOOT", 1: "LV_POWER", 2: "BUS_HEALTH_CHECK", 3: "PRECHARGE", 4: "ENERGIZED",
    5: "DRIVE", 6: "BATTERY_FREE", 7: "CHARGER_PRECHARGE", 8: "CHARGING", 9: "BALANCE",
    10: "FAULT_BMS", 11: "FAULT_BSPD", 12: "FAULT_IMD", 13: "FAULT_CHARGING",
}


def _s16(lo, hi):
    v = lo | (hi << 8)
    return v - 0x10000 if v & 0x8000 else v


class Node:
    def __init__(self, ctx):
        self.ctx = ctx
        self.last_state = None
        self.count = {FRAME_VOLTAGE: 0, FRAME_TEMP: 0}

    def on_frame(self, frame):
        cid = frame["id"]
        data = bytes(frame["data"])
        if cid == FRAME_BMS_STATE and data:
            state = data[0] & 0x1F
            if state != self.last_state:
                name = BMS_STATE_NAMES.get(state, f"state {state}")
                self.ctx.info(f"bms_state frame: {name} ({state})")
                self.last_state = state
        elif cid == FRAME_VOLTAGE and len(data) >= 6:
            self.count[cid] += 1
            if self.count[cid] % LOG_EVERY == 1:
                total = _s16(data[0], data[1]) / 10.0  # total_pack_voltage, 0.1 V
                vmin = _s16(data[2], data[3]) / 10.0   # min_cell_voltage, 0.1 V
                vmax = _s16(data[4], data[5]) / 10.0   # max_cell_voltage, 0.1 V
                self.ctx.info(f"accumulator V: pack {total:.1f} V, cell min {vmin:.1f} V, max {vmax:.1f} V")
        elif cid == FRAME_TEMP and len(data) >= 6:
            self.count[cid] += 1
            if self.count[cid] % LOG_EVERY == 1:
                avg = _s16(data[0], data[1]) / 10.0    # average_pack_temperature, 0.1 degC (DBC bit 0)
                tmin = _s16(data[2], data[3]) / 10.0   # min_cell_temperature (DBC bit 16)
                tmax = _s16(data[4], data[5]) / 10.0   # max_cell_temperature (DBC bit 32)
                self.ctx.info(f"accumulator T: avg {avg:.1f} C, min {tmin:.1f} C, max {tmax:.1f} C")
