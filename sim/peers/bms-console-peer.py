"""Operator console on the SN5 BMS USART2 (115200 8N1), typed by a scripted UART peer.

Firmware: FEB_FIRMWARE_SN5/BMS. The console is FEB_UART_INSTANCE_1 on huart2
(BMS/Core/User/Src/FEB_Main.c FEB_Init). Lines end with \r or \n; the console
dispatches each line on its `|` delimiter (common/FEB_Serial_Library/FEB_Console).
Commands: BMS|status, BMS|cells (cell voltages, the only command that prints
per-cell data), BMS|temps, BMS|state. The firmware prints nothing unsolicited on
this port after the boot banner, so the peer only sends.

The script types one command per entry in SCRIPT, at the virtual time given in
seconds. The firmware's own output is read from the sim's UART log, not here.
"""

SCRIPT = [
    (1.0, "BMS|status"),
    (1.5, "BMS|cells"),
    (2.5, "BMS|state|bus_health"),
    (4.0, "BMS|temps"),
    (5.0, "BMS|state|precharge"),
    (6.5, "BMS|state"),
    (7.5, "BMS|temps"),
    (9.0, "BMS|cells"),
    (9.5, "BMS|state"),
]

TICK_US = 10_000  # 10 ms timer: fine enough for command times with 0.5 s spacing


class Peer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.next = 0
        self.ticks = 0  # the UART context has no now_us: virtual time = ticks * TICK_US
        self.ctx.schedule_periodic(TICK_US)

    def on_byte(self, b):
        pass  # the firmware's echo or prompt is not needed to drive the script

    def on_timer(self):
        self.ticks += 1
        now_s = self.ticks * TICK_US / 1e6
        while self.next < len(SCRIPT) and now_s >= SCRIPT[self.next][0]:
            _, line = SCRIPT[self.next]
            self.ctx.send((line + "\r\n").encode("ascii"))
            self.ctx.info(f"typed: {line}")
            self.next += 1
