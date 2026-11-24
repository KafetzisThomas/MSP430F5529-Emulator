"""
MSP430F5529 MPY32: non-fractional 16-bit hardware multiplier emulation.

Supports all 4 16-bit operation modes:
- MPY  (unsigned multiply)
- MPYS (signed multiply)
- MAC  (unsigned multiply-and-accumulate)
- MACS (signed multiply-and-accumulate)

Emulation simplifications vs real silicon:
- results are available immediately on OP2 write, zero clock latency.
- 8-bit writes (width == 1) always zero extend to 16 bits rather than sign extending in signed modes.
"""


class Multiplier16:
    """
    Emulate the memory mapped 16-bit registers of the MSP430F5529 MPY32 module.

    Base address is 0x04C0.
    Writing operand 1 to an OP1 mode-select register sets the active operation mode.
    Writing operand 2 to the OP2 trigger register (offset 0x08) executes the calculation.
    """

    BASE = 0x04C0

    # Register offsets relative to BASE (0x04C0):
    # - 0x00: MPY    -> OP1: selects 16-bit unsigned multiply
    # - 0x02: MPYS   -> OP1: selects 16-bit signed multiply
    # - 0x04: MAC    -> OP1: selects 16-bit unsigned multiply-and-accumulate
    # - 0x06: MACS   -> OP1: selects 16-bit signed multiply-and-accumulate

    # - 0x08: OP2    -> OP2 trigger register: starts calculation on write

    # - 0x0A: RESLO  -> low 16 bits of the 32-bit result
    # - 0x0C: RESHI  -> high 16 bits of the 32-bit result
    # - 0x0E: SUMEXT -> carry (MAC) or sign extension (MPYS, MACS)

    _MPY = 0
    _MPYS = 2
    _MAC = 4
    _MACS = 6
    _OP2 = 8
    _RESLO = 10
    _RESHI = 12
    _SUMEXT = 14

    def __init__(self) -> None:
        self.operand: int = 0
        self.operand2: int = 0
        self.reslo: int = 0
        self.reshi: int = 0
        self.sumext: int = 0

        # active mode, offset of last OP1 register written
        self.mode: int = self._MPY

    def read(self, address: int, width: int) -> int:
        """
        Read a 16-bit word or 8-bit byte from an MPY32 register.
        """
        offset = address - self.BASE
        values = {
            self._MPY: self.operand,
            self._MPYS: self.operand,
            self._MAC: self.operand,
            self._MACS: self.operand,
            self._OP2: self.operand2,
            self._RESLO: self.reslo,
            self._RESHI: self.reshi,
            self._SUMEXT: self.sumext,
        }
        base = offset & ~1  # word-align to even register offset
        if base not in values:
            raise ValueError("Unsupported MPY32 register access")
        value = values[base]

        # return full word or extract even / odd offset byte
        return value if width == 2 else (value >> (8 * (offset & 1))) & 0xFF

    def write(self, address: int, width: int, value: int) -> None:
        """
        Write a 16-bit word or 8-bit byte to an MPY32 register.

        Writing to an OP1 register updates operand 1 and selects the mode.
        Writing to OP2 updates operand 2 and immediately runs compute().
        Odd-offset writes are word-aligned to the register's even base offset.
        """
        offset = address - self.BASE
        base = offset & ~1  # word-align to even register offset

        # OP1 mode-select registers: store operand 1 and record active mode
        if base in (self._MPY, self._MPYS, self._MAC, self._MACS):
            if width == 1:
                value = value & 0xFF
            self.operand = value & 0xFFFF
            self.mode = base
            return

        # OP2 trigger register: store operand 2 and execute calculation
        if base == self._OP2:
            if width == 1:
                value = value & 0xFF
            self.operand2 = value & 0xFFFF
            self.compute()
            return

        # RESLO and RESHI are writable to preload an initial accumulator for MAC and MACS
        if base == self._RESLO:
            if width == 1:
                value = value & 0xFF
            self.reslo = value & 0xFFFF
            return

        if base == self._RESHI:
            if width == 1:
                value = value & 0xFF
            self.reshi = value & 0xFFFF
            return

        raise ValueError("Unsupported MPY32 register write")

    def compute(self) -> None:
        """
        Execute the 16x16 operation for the active mode and update RESLO, RESHI and SUMEXT.
        """
        op1 = self.operand
        op2 = self.operand2

        if self.mode == self._MPY:
            # unsigned 16 x 16 -> 32-bit product, SUMEXT is always 0
            result = op1 * op2
            self.reslo = result & 0xFFFF
            self.reshi = (result >> 16) & 0xFFFF
            self.sumext = 0

        elif self.mode == self._MPYS:
            # signed 16 x 16 -> 32-bit product
            s1 = op1 if op1 < 0x8000 else op1 - 0x10000
            s2 = op2 if op2 < 0x8000 else op2 - 0x10000
            result = (s1 * s2) & 0xFFFFFFFF
            self.reslo = result & 0xFFFF
            self.reshi = (result >> 16) & 0xFFFF

            # SUMEXT: 0xFFFF if negative, 0x0000 if non-negative
            self.sumext = 0xFFFF if self.reshi & 0x8000 else 0

        elif self.mode == self._MAC:
            # unsigned accumulate: (RESHI:RESLO) + (op1 * op2)
            prev = self.reslo | (self.reshi << 16)
            result = prev + op1 * op2
            self.reslo = result & 0xFFFF
            self.reshi = (result >> 16) & 0xFFFF

            # SUMEXT holds bit 32 (carry out of the 32-bit sum)
            self.sumext = (result >> 32) & 0xFFFF

        elif self.mode == self._MACS:
            # signed accumulate: (RESHI:RESLO) + (s1 * s2)
            s1 = op1 if op1 < 0x8000 else op1 - 0x10000
            s2 = op2 if op2 < 0x8000 else op2 - 0x10000
            prev = self.reslo | (self.reshi << 16)
            if prev & 0x80000000:
                prev -= 0x100000000
            result = (prev + s1 * s2) & 0xFFFFFFFF
            self.reslo = result & 0xFFFF
            self.reshi = (result >> 16) & 0xFFFF

            # SUMEXT reflects the sign of the 32-bit accumulated result
            self.sumext = 0xFFFF if self.reshi & 0x8000 else 0
