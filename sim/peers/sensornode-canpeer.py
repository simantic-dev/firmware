"""Passive CAN node for the FEB SN5 FRONT scenario.

Its job is to be a second node on the bus so the sensor node's transmitted frames get
an ACK (with no other node the firmware sees LEC=ack and drives itself bus-off).
It sends nothing and ignores what it receives; the frames are read from the scenario's
--frames output, not from this script.
"""


class Node:
    def __init__(self, ctx):
        self.ctx = ctx

    def on_frame(self, frame):
        pass
