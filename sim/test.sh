#!/bin/sh
# Runs the prebuilt SN5 car images (sim/fw: BMS, PCU, LVPDB, Sensor_Nodes FRONT and REAR, stripped of
# debug info) on STM32F446 models sharing one CAN bus, with the ADBMS, console, drive-train and sensor
# peers of scenario-test.yaml, 6 virtual seconds. The DCU of the full scenario.yaml is left out: its SD
# image needs mtools. Pass = the boards boot, talk over CAN, and the BMS reaches the same
# states as sim/run.sh asserts (health-check back-out, then FAULT_BMS for want of a current sensor).
cd "$(dirname "$0")" || exit 1
T=$(mktemp -d) || exit 1
trap 'rm -rf "$T"' EXIT
${SIM:-sim} run --scenario scenario-test.yaml --timeout 6 --ascii --frames-only can --frames "$T/can.txt" \
  > "$T/uart.raw" 2> "$T/sim.log"
rc=$?
# strip the log colours (the sim prints ESC as '.') and the stream arrows
sed 's/\.\[[0-9;]*m//g; s/ → [a-z0-9]*)/)/' "$T/uart.raw" > "$T/uart.txt"
fail=0
[ $rc -eq 0 ] || { echo "FAIL sim exit $rc"; fail=1; }
need() { if grep -a -q -E "$2" "$T/$1"; then echo "ok   $3"; else echo "FAIL $3"; fail=1; fi; }
need uart.txt '^\[bms\].*BOOT -> LV_POWER' "BMS boots to LV_POWER"
need uart.txt '^\[bms\].*LV_POWER -> BUS_HEALTH_CHECK' "BMS takes the console-requested step to BUS_HEALTH_CHECK"
need uart.txt '^\[bms\].*Shutdown open during health check, returning to LV_POWER' "BMS backs out: shutdown loop open"
need uart.txt '^\[bms\].*FAULT ENTRY: FAULT_BMS' "BMS faults in PRECHARGE (no current sensor)"
need uart.txt '^\[bms\].*Pack Voltage: [0-9.]+V' "BMS console reports pack voltage from the ADBMS chain"
need uart.txt '^\[pcu\].*PCU Setup Complete ===' "PCU finishes its 8-step setup"
need uart.txt '^\[lvpdb\].*TPS init: 7/7 chips OK' "LVPDB finds all seven TPS2482"
need uart.txt '^\[front\].*Gyro auto-cal done' "FRONT sensor node calibrates its gyro"
need uart.txt '^\[rear\].*Gyro auto-cal done' "REAR sensor node calibrates its gyro"
need can.txt '^\[bms\] .*CAN Tx id=0x5 ' "BMS sends bms_state (0x5)"
need can.txt '^\[pcu\] .*CAN Rx id=0x5 ' "PCU receives bms_state from the real BMS"
need can.txt '^\[front\] .*CAN Tx id=0x26 ' "FRONT sends its IMU acceleration frame (0x26)"
need can.txt '^\[rear\] .*CAN Tx id=0x27 ' "REAR sends its IMU acceleration frame (0x27)"
need can.txt '^\[pcu\] .*CAN Tx id=0xC0 ' "PCU sends torque commands (0xC0)"
exit $fail
