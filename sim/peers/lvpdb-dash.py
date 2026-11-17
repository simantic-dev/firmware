"""DASH stand-in on the car CAN bus: sends the dash_state frame the LVPDB reads.

Frame 0x10 (FEB_CAN_DASH_STATE_FRAME_ID, feb_can_db.h, 100 ms cycle). Byte 0 bit 4 is
switch1 (-> AF1_AF2 accumulator fans) and bit 5 is switch2 (-> CP_RF coolant pump and
radiator fans), per feb_can_dash_state_unpack in common/FEB_CAN_Library_SN4/gen/feb_can_db.c.
The LVPDB only applies the switches while the frame is fresh (250 ms, FEB_CAN_DASH.c).

MODELED SIMPLIFICATION: the driver flips both switches on at 1.0 s and leaves them on.
The 100 ms cadence is the DBC cycle time, not invented.
"""

SWITCHES_ON_AT_S = 1.0  # MODELED: driver turns on the pump and fans at 1.0 s
PERIOD_US = 100_000  # FEB_CAN_DASH_STATE_CYCLE_TIME_MS = 100


class Node:
    def __init__(self, ctx):
        self.ctx = ctx
        self.ticks = 0
        self.ctx.schedule_periodic(PERIOD_US)

    def on_timer(self):
        self.ticks += 1
        t = self.ticks * PERIOD_US / 1e6  # virtual time this frame goes out (periodic fires at period end)
        byte0 = 0x30 if t >= SWITCHES_ON_AT_S else 0x00  # switch1 | switch2
        self.ctx.send(0x10, bytes([byte0, 0x00]))

    def on_frame(self, frame):
        pass  # the DASH stand-in only transmits
