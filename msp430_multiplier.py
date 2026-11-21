"""Partial F5529 MPY32: non-fractional 16-bit unsigned multiply only.

Other multiplier registers and operations are not modeled here. Results become
available immediately rather than after the hardware's documented latency.
"""


class UnsignedMultiplier16:
    BASE = 0x04c0

    def __init__(self):
        self.operand = 0
        self.operand2 = 0
        self.result = 0

    def read(self, address, width):
        offset = address - self.BASE
        values = {0: self.operand, 8: self.operand2,
                  10: self.result & 0xffff, 12: (self.result >> 16) & 0xffff,
                  14: 0}
        base = offset & ~1
        if base not in values:
            raise ValueError('Unsupported MPY32 register access')
        value = values[base]
        return value if width == 2 else (value >> (8 * (offset & 1))) & 0xff

    def write(self, address, width, value):
        offset = address - self.BASE
        if width != 2 or offset not in (0, 8):
            raise ValueError('Only word writes to MPY and OP2 are supported')
        if offset == 0:
            self.operand = value
        else:
            self.operand2 = value
            self.result = self.operand * value
