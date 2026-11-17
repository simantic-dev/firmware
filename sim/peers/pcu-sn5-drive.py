"""Drive the FEB SN5 PCU firmware through a pedal and brake sequence in the simulator.

Firmware: FEB_FIRMWARE_SN5/PCU (build/Debug/PCU/PCU.elf), STM32F446RE.
Peer: this script. It plays three things the PCU reads or hears on the car:

  * the accelerator pedal (APPS1 on ADC3 ch13 = PC3, APPS2 on ADC3 ch12 = PC2),
  * the brake (BP1 on ADC1 ch1 = PA1, BP2 on ADC1 ch0 = PA0, brake switch line
    on ADC1 ch14 = PC4),
  * the BMS state frame (CAN id 0x005, state in data[0] & 0x1F) that gates
    FEB_CAN_BMS_InDriveState(). Drive state is what enables the inverter in this
    firmware; the PCU does not read the ready-to-drive button (PB7 is only
    defined in FEB_PINOUT.h, never read).

What the PCU writes back and what this script records:

  * CAN id 0xC0 (M192 torque command), sent every 20 ms from FEB_RMS_Torque:
    bytes 0..1 torque in tenths of Nm (int16 LE), byte 5 bit 0 inverter enable.
  * UART2 log (FEB_Log, 115200): the APPS / brake / drive-state messages.

Vendored module: pcu-can-peer.py imports scenario() and decode_torque(); pcu-gen-points.py
samples it for the ADC points in ../pcu.yaml. Self-check: python3 -c "import runpy; runpy.run_path('pcu-sn5-drive.py')['selfcheck']()"
"""

import struct

# --- firmware constants (cited: FEB_PINOUT.h and FEB_ADC.c unless noted) -----

APPS1_MIN_MV, APPS1_MAX_MV = 1375, 2356  # APPS1_DEFAULT_*_VOLTAGE_MV, sensor side
APPS2_MIN_MV, APPS2_MAX_MV = 539, 1320  # APPS2_DEFAULT_*_VOLTAGE_MV, sensor side
APPS1_DIVIDER = 1.168  # FEB_ADC.c VOLTAGE_DIVIDER_RATIO_ACCEL1 (sensor V = ADC V * ratio)
APPS2_DIVIDER = 1.0  # FEB_ADC.c VOLTAGE_DIVIDER_RATIO_ACCEL2
BP1_MIN_MV, BP1_MAX_MV = 428, 997  # BRAKE_PRESSURE_1_*_MV, sensor side
BP2_MIN_MV, BP2_MAX_MV = 576, 1512  # BRAKE_PRESSURE_2_*_MV, sensor side
BRAKE_DIVIDER = 5.0 / 3.3  # FEB_ADC.c VOLTAGE_DIVIDER_RATIO_BRAKE

TORQUE_CMD_ID = 0xC0  # FEB_CAN_M192_COMMAND_MESSAGE_FRAME_ID
BMS_STATE_ID = 0x005  # FEB_CAN_BMS_STATE_FRAME_ID
BMS_STATE_ENERGIZED = 4  # FEB_SM_ST_ENERGIZED
BMS_STATE_DRIVE = 5  # FEB_SM_ST_DRIVE
BMS_STATE_PERIOD_MS = 100  # MODELED SIMPLIFICATION: BMS state broadcast rate. The
# firmware only requires a frame within BMS_STATE_TIMEOUT_MS = 500 (FEB_CAN_BMS.c);
# the real BMS period is not in this tree.

# Pins that carry each signal on the PCU board (names as the sim's ADC peripherals).
ADC_APPS = "adc3"
ADC_APPS1_CH, ADC_APPS2_CH = 13, 12
ADC_BRAKE = "adc1"
ADC_BP1_CH, ADC_BP2_CH, ADC_BRAKE_SWITCH_CH = 1, 0, 14
CAN = "can1"

STEP_S = 0.01  # 10 ms stimulus step. MODELED SIMPLIFICATION: real pedal sensors
# move continuously; the firmware samples at 10 kHz and averages, so a 10 ms
# staircase is coarser than the pedal but well inside the 100 ms fault window.


def apps_pin_volts(pedal_pct, apps2_offset_pct=0.0):
    """Pin voltages (ADC side) that give `pedal_pct` on APPS1 and `pedal_pct + offset` on APPS2."""
    s1 = APPS1_MIN_MV + (APPS1_MAX_MV - APPS1_MIN_MV) * pedal_pct / 100.0
    p2 = pedal_pct + apps2_offset_pct
    s2 = APPS2_MIN_MV + (APPS2_MAX_MV - APPS2_MIN_MV) * p2 / 100.0
    return s1 / 1000.0 / APPS1_DIVIDER, s2 / 1000.0 / APPS2_DIVIDER


def brake_pin_volts(brake_pct):
    """Pin voltages for BP1, BP2 and the brake switch line at `brake_pct` brake pressure."""
    bp1 = BP1_MIN_MV + (BP1_MAX_MV - BP1_MIN_MV) * brake_pct / 100.0
    bp2 = BP2_MIN_MV + (BP2_MAX_MV - BP2_MIN_MV) * brake_pct / 100.0
    # MODELED SIMPLIFICATION: the brake switch line is tied to sensor 1, so the
    # firmware's "which sensor is shorted to the switch" test picks BP1. The
    # switch wiring on the car is not in the source tree.
    return bp1 / 1000.0 / BRAKE_DIVIDER, bp2 / 1000.0 / BRAKE_DIVIDER, bp1 / 1000.0 / BRAKE_DIVIDER


def scenario(t):
    """Return (pedal %, APPS2 offset %, brake %, BMS state) at virtual time t seconds.

    MODELED SIMPLIFICATION: the sequence and its percentages are chosen for this
    use case, not measured from a driver. The 12 % APPS2 offset is the
    disagreement the task asks for; it is above the 10 % limit
    (APPS_PLAUSIBILITY_TOLERANCE) and held for 1 s, above the 100 ms latch time.
    """
    pedal, offset, brake, bms = 0.0, 0.0, 0.0, BMS_STATE_ENERGIZED
    if t >= 1.0:
        brake = 60.0  # brake pressed before ready-to-drive
    if t >= 2.0:
        bms = BMS_STATE_DRIVE  # BMS enters drive with the brake still held
    if t >= 3.0:
        brake = 0.0  # brake released
    if 3.5 <= t < 6.5:
        pedal = 100.0 * (t - 3.5) / 3.0  # throttle ramp 0 -> 100 % over 3 s
    if 6.5 <= t < 7.0:
        pedal = 100.0 * (7.0 - t) / 0.5  # release 100 % -> 0 over 0.5 s
    if 7.0 <= t < 8.0:
        brake = 60.0  # brake applied with throttle at zero
    if t >= 8.0:
        brake = 0.0
    if 8.5 <= t:
        pedal = 40.0  # part throttle for the disagreement test
    if t >= 9.0:
        offset = -12.0  # APPS2 reads 12 % below APPS1
    return pedal, offset, brake, bms


def decode_torque(data):
    """M192 frame: torque tenths-Nm (int16 LE) and inverter enable (byte 5 bit 0)."""
    torque = struct.unpack_from("<h", bytes(data), 0)[0]
    enable = bytes(data)[5] & 0x01
    return torque / 10.0, enable


def selfcheck():
    # Pin volts at rest and at full scale reproduce the firmware's sensor-side calibration.
    v1, v2 = apps_pin_volts(0.0)
    assert abs(v1 * APPS1_DIVIDER * 1000 - APPS1_MIN_MV) < 1e-6
    assert abs(v2 * APPS2_DIVIDER * 1000 - APPS2_MIN_MV) < 1e-6
    v1, v2 = apps_pin_volts(100.0)
    assert abs(v1 * APPS1_DIVIDER * 1000 - APPS1_MAX_MV) < 1e-6
    assert abs(v2 * APPS2_DIVIDER * 1000 - APPS2_MAX_MV) < 1e-6
    # The disagreement is exactly the offset, in percent of travel.
    _, offset, _, _ = scenario(9.5)
    assert offset == -12.0
    # Torque frame: -25.0 Nm enable 1.
    data = struct.pack("<h", -250) + bytes([0, 0, 0, 0x01, 0, 0])
    assert decode_torque(data) == (-25.0, 1)
    print("pcu-sn5-drive selfcheck ok")
