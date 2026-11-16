"""CAN peer for the FEB SN5 PCU drive scenario (pcu-sn5.scenario.yaml).

Sends the BMS state frame (CAN id 0x005, state in data[0] & 0x1F) every 100 ms and
logs every torque command the PCU sends (CAN id 0xC0, M192) decoded as Nm and enable.

The BMS state comes from pcu-sn5-drive.py scenario(): ENERGIZED until 2.0 s, then DRIVE.
Frames are sent from t = 0 so the PCU never sees a stale BMS state (the firmware's
timeout is 500 ms); the driver does the same.

Time: a scripted CAN node has no virtual clock, so this peer counts its own 1 ms
timer. The log time is therefore accurate to about 1 ms; the --frames output has the
exact frame times.

The drive module is loaded from peers/ under the working directory: run sim from sim/.
"""

import importlib.util
import os

_spec = importlib.util.spec_from_file_location("pcu_drive", os.path.join(os.getcwd(), "peers", "pcu-sn5-drive.py"))
drive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drive)

BMS_STATE_ID = drive.BMS_STATE_ID
TORQUE_CMD_ID = drive.TORQUE_CMD_ID
BMS_PERIOD_US = 100_000
TICK_US = 1_000  # 1 ms virtual time per timer fire


class Node:
    def __init__(self, ctx):
        self.ctx = ctx
        self.now_us = 0
        self.next_bms_us = 0
        self.ctx.schedule_periodic(TICK_US)

    def on_timer(self):
        self.now_us += TICK_US
        if self.now_us >= self.next_bms_us:
            _, _, _, bms = drive.scenario(self.next_bms_us / 1e6)
            self.ctx.send(BMS_STATE_ID, bytes([bms]) + bytes(7))
            self.next_bms_us += BMS_PERIOD_US

    def on_frame(self, frame):
        if frame["id"] != TORQUE_CMD_ID:
            return
        torque, enable = drive.decode_torque(frame["data"])
        self.ctx.info(f"t={self.now_us / 1e6:.3f}s torque_cmd {torque:.1f} Nm enable={enable}")
