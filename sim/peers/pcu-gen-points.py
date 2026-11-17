"""Generate the analog: points for pcu-sn5.scenario.yaml from pcu-sn5-drive.py.

Samples the driver's scenario(t) and brake/APPS maths every 10 ms (the driver's own
STEP_S), then drops samples that lie on the line between their neighbours, so only
the corners of each ramp and step are written. Prints the YAML block to stdout.

Run from sim/peers/:  python3 -I pcu-gen-points.py

MODELED SIMPLIFICATION: the pedal is capped at 95 % (the driver ramps to 100 %). At
100 % APPS2 reads 1320 mV at the sensor, over the 1300 mV open-circuit limit; at 95 %
it reads 1281 mV. The cap is applied here, not in the driver.
"""

import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("pcu_drive", os.path.join(HERE, "pcu-sn5-drive.py"))
drive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drive)

PEDAL_CAP_PCT = 95.0
END_S = 10.0
STEP_S = drive.STEP_S
EPS = 1e-9
CHANNELS = [("adc3", 13), ("adc3", 12), ("adc1", 1), ("adc1", 0), ("adc1", 14)]


def samples():
    rows = []
    for i in range(int(round(END_S / STEP_S)) + 1):
        t = round(i * STEP_S, 6)
        pedal, offset, brake, _bms = drive.scenario(t)
        pedal = min(pedal, PEDAL_CAP_PCT)
        v1, v2 = drive.apps_pin_volts(pedal, offset)
        bp1, bp2, bsw = drive.brake_pin_volts(brake)
        volts = {("adc3", 13): v1, ("adc3", 12): v2,
                 ("adc1", 1): bp1, ("adc1", 0): bp2, ("adc1", 14): bsw}
        rows.append((t, volts))
    return rows


def reduce(points):
    """Keep only the vertices of a piecewise-linear series."""
    if len(points) <= 2:
        return points
    keep = [points[0]]
    for prev, cur, nxt in zip(points, points[1:], points[2:]):
        slope1 = (cur[1] - prev[1]) / (cur[0] - prev[0])
        slope2 = (nxt[1] - cur[1]) / (nxt[0] - cur[0])
        if abs(slope1 - slope2) > EPS:
            keep.append(cur)
    keep.append(points[-1])
    return keep


def main():
    rows = samples()
    print("analog:")
    for adc, ch in CHANNELS:
        pts = reduce([(t, v[(adc, ch)]) for t, v in rows])
        body = ", ".join(f"[{t:g}, {v:.6f}]" for t, v in pts)
        print(f"  - {{ adc: {adc}, channel: {ch}, points: [{body}] }}")


if __name__ == "__main__":
    main()
