"""LIS3MDL magnetometer (7-bit 0x1C on I2C3) for the FEB SN5 FRONT sensor node.

Firmware: FEB_FIRMWARE_SN5/Sensor_Nodes Core/User/Src/FEB_Magnetometer.c (lis3mdl_init,
read_Magnetic_Field_Data). WHO_AM_I (0x0F, expects 0x3D), then 155 Hz UHP, +/-16 gauss,
continuous mode. Output OUT_X_L 0x28..0x2D, auto-increment set by bit 7 of the sub-address.
Sensitivity at +/-16 gauss: 1711 LSB/gauss (LIS3MDL datasheet, Table 3).

Run from feb-peers/ together with sensornode-lsm6dsox.py (see sensornode-front.board).
"""

# MODELED SIMPLIFICATION: horizontal field 0.25 gauss (Earth-field scale, no local anomaly),
# vertical component -0.40 gauss, rotated about z by the heading the gyro integrates to
# (the same corner as sensornode-lsm6dsox.py). No hard or soft iron, no noise.
import math

WHO_AM_I = 0x3D
LSB_PER_GAUSS = 1711.0
B_H = 0.25
B_Z = -0.40


def heading_deg(t):
    """Integral of the corner yaw rate: 25 dps * sin over 2 s = 25 * 2/pi * (1 - cos) deg."""
    if t < 5.5:
        return 0.0
    u = min(t, 7.5) - 5.5
    return 25.0 * (2.0 / math.pi) * (1.0 - math.cos(math.pi * u / 2.0))


def field(t):
    th = math.radians(heading_deg(t))
    return (B_H * math.cos(th), B_H * math.sin(th), B_Z)


def _s16(v):
    v = int(round(v))
    v = max(-32768, min(32767, v))
    return v & 0xFFFF


class Slave:
    def __init__(self, ctx):
        self.ctx = ctx
        self.regs = {0x0F: WHO_AM_I}
        self.ptr = 0

    def on_write(self, data):
        if not data:
            return
        self.ptr = data[0] & 0x7F
        for i, b in enumerate(data[1:]):
            self.regs[self.ptr + i] = b
        self.ptr += len(data) - 1

    def on_read(self, count):
        t = self.ctx.now_us / 1e6
        bx, by, bz = field(t)
        words = [_s16(bx * LSB_PER_GAUSS), _s16(by * LSB_PER_GAUSS), _s16(bz * LSB_PER_GAUSS)]
        sample = {}
        for i, w in enumerate(words):
            sample[0x28 + 2 * i] = w & 0xFF
            sample[0x29 + 2 * i] = w >> 8
        out = bytearray()
        for _ in range(count):
            p = self.ptr & 0x7F
            out.append(sample.get(p, self.regs.get(p, 0)))
            self.ptr += 1
        return bytes(out)
