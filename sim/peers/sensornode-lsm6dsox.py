"""LSM6DSOX IMU (7-bit 0x6A on I2C3) for the FEB SN5 FRONT sensor node.

Firmware: FEB_FIRMWARE_SN5/Sensor_Nodes Core/User/Src/FEB_IMU.c (lsm6dsox_init,
read_Acceleration, read_Angular_Rate). The firmware reads WHO_AM_I (0x0F, expects
0x6C), writes CTRL3_C.SW_RESET (bit 0, self-clearing), then sets 6.667 kHz ODR,
+/-2 g and +/-2000 dps. Accel raw is OUTX_L_A 0x28..0x2D, gyro raw OUTX_L_G 0x22..0x27.

Sensitivities (LSM6DSOX datasheet, Table 3): 2 g = 0.061 mg/LSB, 2000 dps = 70 mdps/LSB.

Run from feb-peers/: sim STM32F446RE run --elf <FRONT.elf> --board sensornode-front.board --timeout 10
"""

# MODELED SIMPLIFICATION: the whole drive profile below is invented, not logged from a car.
# Stand-in for the vehicle: 2 s at rest, 0.4 g accel 2-5 s, 0.9 g brake 5-6 s,
# and a 2 s corner 5.5-7.5 s with 25 dps peak yaw and 0.45 g lateral (trail-braking
# is not modelled). Times are virtual seconds from ctx.now_us.

import math

WHO_AM_I = 0x6C
G_PER_LSB = 0.061e-3
DPS_PER_LSB = 70e-3


def _ramp(t, t0, t1, peak):
    """Trapezoid from 0 up to peak and back, between t0 and t1, 0.5 s ramps."""
    if t < t0 or t > t1:
        return 0.0
    r = 0.5
    if t < t0 + r:
        return peak * (t - t0) / r
    if t > t1 - r:
        return peak * (t1 - t) / r
    return peak


def profile(t):
    """(ax, ay, az) in g, (gx, gy, gz) in dps at virtual time t seconds."""
    ax = _ramp(t, 2.0, 5.0, 0.4) + _ramp(t, 5.0, 6.0, -0.9)
    ay = 0.0
    gz = 0.0
    if 5.5 <= t <= 7.5:
        s = math.sin(math.pi * (t - 5.5) / 2.0)
        gz = 25.0 * s
        ay = 0.45 * s
    az = 1.0  # gravity, board flat
    return (ax, ay, az), (0.0, 0.0, gz)


def _s16(v):
    v = int(round(v))
    v = max(-32768, min(32767, v))
    return v & 0xFFFF


class Slave:
    def __init__(self, ctx):
        self.ctx = ctx
        self.regs = {0x0F: WHO_AM_I, 0x12: 0x04}  # CTRL3_C default: IF_INC
        self.ptr = 0
        self._logged = False

    def _sample(self):
        t = self.ctx.now_us / 1e6
        (ax, ay, az), (gx, gy, gz) = profile(t)
        vals = [
            _s16(gx / DPS_PER_LSB), _s16(gy / DPS_PER_LSB), _s16(gz / DPS_PER_LSB),
            _s16(ax / G_PER_LSB), _s16(ay / G_PER_LSB), _s16(az / G_PER_LSB),
        ]
        out = {}
        for i, v in enumerate(vals):
            out[0x22 + 2 * i] = v & 0xFF
            out[0x23 + 2 * i] = v >> 8
        return out

    def on_write(self, data):
        if not data:
            return
        self.ptr = data[0]
        for i, b in enumerate(data[1:]):
            reg = self.ptr + i
            if reg == 0x12 and (b & 0x01):  # SW_RESET self-clears
                b &= ~0x01
                self.ctx.info("SW_RESET")
            self.regs[reg] = b
        self.ptr += len(data) - 1

    def on_read(self, count):
        if not self._logged:
            self._logged = True
            self.ctx.info("first read")
        out = bytearray()
        sample = self._sample()
        for _ in range(count):
            p = self.ptr
            if 0x22 <= p <= 0x2D:
                b = sample[p]
            else:
                b = self.regs.get(p, 0)
            out.append(b)
            self.ptr += 1
        return bytes(out)
