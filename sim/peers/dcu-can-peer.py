"""CAN traffic from the other SN5 boards, as seen on the DCU's CAN1 bus.

Firmware: FEB_FIRMWARE_SN5/DCU (accept-all wildcard capture on CAN1 and CAN2).
Message layouts: FEB_FIRMWARE_SN5/common/FEB_CAN_Library_SN4/gen/FEB_CAN.dbc
(Intel byte order, "start|len@1"). Cadences: the DCU allow-list in
DCU/Core/User/Src/DCU_CAN_Filter.c where it names one, otherwise a plausible rate.

One periodic timer at 10 ms of virtual time; every tick the script sends whatever is
due. Values are raw DBC counts (scale 1 unless the DBC says otherwise). Physical
units are NOT verified against the BMS/SN firmware encoders.

MODELED SIMPLIFICATION: no heartbeats (0xD4/0xD5, layout not in the DBC), no IMU
(0x26/0x38-0x3A), no GPS, no inverter (0xA0-0xB0) traffic. Those are not sent.
"""

TICK_US = 10_000  # 10 ms virtual time per timer fire


def pack(payload, value, start, length):
    """Write `value` into a little-endian DBC signal at bit `start`, `length` bits wide."""
    value &= (1 << length) - 1
    for i in range(length):
        bit = start + i
        if (value >> i) & 1:
            payload[bit // 8] |= 1 << (bit % 8)
    return payload


def frame(signals, dlc=8):
    data = [0] * dlc
    for value, start, length in signals:
        pack(data, value, start, length)
    return bytes(data)


class Node:
    def __init__(self, ctx):
        self.ctx = ctx
        self.n = 0  # timer fires so far; virtual time = n * TICK_US
        self.ctx.schedule_periodic(TICK_US)

    def ms(self):
        return (self.n * TICK_US // 1000) & 0xFFFF

    def on_timer(self):
        self.n += 1
        n = self.n
        ms = self.ms()

        # BMS: accumulator voltage (id 2) and temperature (id 3), 10 Hz.
        if n % 10 == 0:
            self.ctx.send(2, frame([
                (3700 * 10, 0, 16),    # total_pack_voltage
                (3702, 16, 16),        # min_cell_voltage (mV)
                (3710, 32, 16),        # max_cell_voltage (mV)
                (ms, 48, 16),          # send_time (ms)
            ]))
            self.ctx.send(3, frame([
                (25, 0, 16),           # average_pack_temperature (signed)
                (21, 16, 16),          # min_cell_temperature (signed)
                (31, 32, 16),          # max_cell_temperature (signed)
                (ms, 48, 16),          # send_time (ms)
            ]))

        # BMS: bms_state (id 5), 10 Hz. bms_state 0..31, relay_state 3 bits.
        if n % 10 == 0:
            self.ctx.send(5, frame([
                (2, 0, 5),             # bms_state = 2
                (0, 8, 3),             # relay_state = open
                (0, 5, 3),             # ping_lv_nodes
                (0, 11, 5),            # gpio_sense
            ], dlc=2))

        # BMS: accumulator_faults (id 4), 2 Hz, no faults.
        if n % 50 == 0:
            self.ctx.send(4, frame([(0, 0, 1), (0, 1, 1)], dlc=1))

        # BMS: bms_cell_data (id 1), one bank frame per 50 ms, banks 0..9 round-robin.
        # Each frame carries cells 0..3 of its bank; full 10 x 12 coverage is not needed here.
        if n % 5 == 0:
            bank = (n // 5) % 10
            self.ctx.send(1, frame([
                (0, 0, 4),             # bms_flags
                (0, 8, 4),             # bms_cell (first cell in the frame)
                (bank, 12, 4),         # bms_bank
                (3700 + bank, 16, 16), # bms_voltage (mV)
                (25, 32, 16),          # bms_temperature (signed)
                (ms, 48, 16),          # bms_send_time (ms)
            ]))

        # Front sensor node: tire temperatures (ids 0x20/0x21), every 2 s.
        if n % 200 == 0:
            self.ctx.send(0x20, frame([(310 + i, 16 * i, 16) for i in range(4)]))
            self.ctx.send(0x21, frame([(312 + i, 16 * i, 16) for i in range(4)]))

        # Rear sensor node: tire temperatures (ids 0x22/0x23), every 2 s.
        if n % 200 == 100:
            self.ctx.send(0x22, frame([(308 + i, 16 * i, 16) for i in range(4)]))
            self.ctx.send(0x23, frame([(309 + i, 16 * i, 16) for i in range(4)]))

        # Wheel speed (DBC wss_front_data id 0x24, wss_rear_data id 0x25), 4 Hz.
        # Raw = mph / 0.01, so 12.34 mph -> 1234. dir_flags at bit 32.
        if n % 25 == 0:
            speed = 1234
            self.ctx.send(0x24, frame([
                (speed, 0, 16),        # wss_left_front
                (speed, 16, 16),       # wss_right_front
                (0, 32, 8),            # wss_dir_flags
            ]))
            self.ctx.send(0x25, frame([
                (speed, 0, 16),        # wss_left_rear (DBC name, Rear)
                (speed, 16, 16),       # wss_right_rear
                (0, 32, 8),            # wss_dir_flags
            ]))

    def on_frame(self, frame):
        pass  # the DCU is a pure sink; nothing it sends on CAN is answered
