"""Experimental classic MSP430 instruction subset; not a full CPUX emulator."""
import struct
from msp430_memory import Memory
from msp430_multiplier import UnsignedMultiplier16


class UnsupportedInstruction(Exception):
    pass


class CPU:
    def __init__(self, elf):
        if elf[:6] != b'\x7fELF\x01\x01':
            raise ValueError('Expected little-endian ELF32 firmware')
        self.memory = Memory()
        self.multiplier = UnsignedMultiplier16()
        self.memory.map_region(0x04c0, 0x04cf, self.multiplier)
        # Compatibility view for firmware loading and existing inspection tools.
        # CPU instruction accesses must use the memory interface instead.
        self.mem = self.memory.data
        self.reg = [0] * 16
        phoff = struct.unpack_from('<I', elf, 28)[0]
        entsize, count = struct.unpack_from('<HH', elf, 42)
        for i in range(count):
            typ, offset, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from('<8I', elf, phoff + i * entsize)
            if typ == 1 and filesz:
                if paddr + filesz > len(self.mem) or offset + filesz > len(elf):
                    raise ValueError('ELF segment outside memory or file')
                self.memory.load(paddr, elf[offset:offset + filesz])
        self.reg[0] = self.read16(0xfffe)
        self.instructions = 0
        self.cycles = 0

    def read8(self, addr):
        return self.memory.read(addr, 1)

    def write8(self, addr, value):
        self.memory.write(addr, 1, value)

    def read16(self, addr):
        return self.memory.read(addr, 2)

    def write16(self, addr, value):
        self.memory.write(addr, 2, value)

    def fetch(self):
        value = self.read16(self.reg[0])
        self.reg[0] = (self.reg[0] + 2) & 0xffff
        return value

    def step(self):
        pc = self.reg[0]
        op = self.fetch()
        self.instructions += 1
        if op & 0xe000 == 0x2000:
            cond = (op >> 10) & 7
            sr = self.reg[2]
            z, c, n, v = bool(sr & 2), bool(sr & 1), bool(sr & 4), bool(sr & 0x100)
            take = (not z, z, not c, c, n, n == v, n != v, True)[cond]
            delta = op & 0x3ff
            if delta & 0x200:
                delta -= 0x400
            if take:
                self.reg[0] = (self.reg[0] + 2 * delta) & 0xffff
            self.cycles += 2
            return
        # Format II: general registers and selected memory addressing modes.
        operation = op & 0xff80
        if operation in (0x1000, 0x1080, 0x1100, 0x1180, 0x1200):
            byte = bool(op & 0x40)
            mode, dst = (op >> 4) & 3, op & 15
            if dst < 4 or mode == 3 or (byte and operation in (0x1080, 0x1180)):
                raise UnsupportedInstruction(f'Unsupported instruction 0x{op:04x} at 0x{pc:04x}')
            address = None
            if mode == 0:
                value = self.reg[dst] & (0xff if byte else 0xffff)
            else:
                offset = self.fetch() if mode == 1 else 0
                address = (self.reg[dst] + offset) & 0xffff
                value = self.read8(address) if byte else self.read16(address)
            if operation == 0x1200:
                self.reg[1] = (self.reg[1] - 2) & 0xffff
                if byte:
                    self.write8(self.reg[1], value)
                else:
                    self.write16(self.reg[1], value)
                self.cycles += 4 if mode == 1 else 3
                return
            sign = 0x80 if byte else 0x8000
            if operation == 0x1000:
                result = (value >> 1) | (sign if self.reg[2] & 1 else 0)
                carry = value & 1
            elif operation == 0x1080:
                result = ((value & 0xff) << 8) | (value >> 8)
            elif operation == 0x1100:
                result = (value >> 1) | (value & sign)
                carry = value & 1
            else:
                result = (value & 0xff) | ((0xfff00 if address is None else 0xff00) if value & 0x80 else 0)
                sign = 0x80000 if address is None else 0x8000
                carry = int(result != 0)
            if address is None:
                self.reg[dst] = result
            elif byte:
                self.write8(address, result)
            else:
                self.write16(address, result)
            if operation != 0x1080:
                self.reg[2] = ((self.reg[2] & ~0x107) | carry |
                               (2 if result == 0 else 0) |
                               (4 if result & sign else 0))
            self.cycles += (1, 4, 3)[mode]
            return
        if op & 0xfff0 == 0x1280 and (op & 15) >= 4:
            target = self.reg[op & 15] & 0xffff
            self.reg[1] = (self.reg[1] - 2) & 0xffff
            self.write16(self.reg[1], self.reg[0])
            self.reg[0] = target
            self.cycles += 4
            return
        if op == 0x12b0:
            target = self.fetch()
            self.reg[1] = (self.reg[1] - 2) & 0xffff
            self.write16(self.reg[1], self.reg[0])
            self.reg[0] = target
            self.cycles += 4
            return
        code = op >> 12
        if code not in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15):
            raise UnsupportedInstruction(f'Unsupported instruction 0x{op:04x} at 0x{pc:04x}')
        src, dst = (op >> 8) & 15, op & 15
        ad, byte, mode = (op >> 7) & 1, bool(op & 0x40), (op >> 4) & 3
        # TI SLAU208Q table 6-10: classic format-I instruction timing.
        constant = src == 3 or (src == 2 and mode >= 2)
        if constant or mode == 0:
            source_class = 'register'
        elif src == 0 and mode == 3:
            source_class = 'immediate'
        elif mode == 1:
            source_class = 'indexed'
        else:
            source_class = 'indirect'
        if ad:
            cycles = {'register': 4, 'immediate': 5, 'indirect': 5, 'indexed': 6}[source_class]
            if code in (4, 9, 11):
                cycles -= 1
        elif dst == 0:
            cycles = {'register': 3, 'immediate': 3, 'indirect': 4, 'indexed': 5}[source_class]
        else:
            cycles = {'register': 1, 'immediate': 2, 'indirect': 2, 'indexed': 3}[source_class]
        self.cycles += cycles
        mask = 0xff if byte else 0xffff
        if src == 3:
            value = (0, 1, 2, mask)[mode]
        elif src == 2 and mode >= 2:
            value = (4, 8)[mode - 2]
        elif mode == 0:
            value = self.reg[src]
        elif mode == 3 and src == 0:
            value = self.fetch()
        else:
            if mode == 1:
                offset = self.fetch()
                address = offset if src == 2 else (self.reg[src] + offset) & 0xffff
            else:
                address = self.reg[src]
                if mode == 3:
                    self.reg[src] = (self.reg[src] + (1 if byte and src != 1 else 2)) & 0xffff
            value = self.read8(address) if byte else self.read16(address)
        value &= mask
        if ad:
            offset = self.fetch()
            address = offset if dst == 2 else (self.reg[dst] + offset) & 0xffff
            original = (self.read8(address) if byte else self.read16(address)) if code != 4 else 0
        else:
            address = None
            original = self.reg[dst] & mask
        if code == 4:
            result = value
        elif code in (5, 6):
            result = original + value + (int(bool(self.reg[2] & 1)) if code == 6 else 0)
        elif code in (7, 8, 9):
            result = original + (~value & mask) + (int(bool(self.reg[2] & 1)) if code == 7 else 1)
        elif code == 10:
            # Packed BCD addition; non-BCD digits have undefined hardware results.
            decimal_carry = int(bool(self.reg[2] & 1))
            result = 0
            for shift in range(0, 8 if byte else 16, 4):
                digit = ((original >> shift) & 15) + ((value >> shift) & 15) + decimal_carry
                decimal_carry = int(digit > 9)
                result |= (digit - 10 if decimal_carry else digit) << shift
        elif code == 12:
            result = original & ~value
        elif code == 13:
            result = original | value
        elif code == 14:
            result = original ^ value
        else:
            result = original & value
        if code == 10:
            # V is undefined by the hardware specification; preserve it deterministically.
            self.reg[2] = ((self.reg[2] & ~7) | decimal_carry |
                           (2 if result == 0 else 0) |
                           (4 if result & (0x80 if byte else 0x8000) else 0))
        elif code in (5, 6, 7, 8, 9, 11, 14, 15):
            r = result & mask
            sign = 0x80 if byte else 0x8000
            carry = result > mask if code in (5, 6, 7, 8, 9) else bool(r)
            overflow = (((~(original ^ value) & (original ^ r)) if code in (5, 6) else
                         ((original ^ value) & (original ^ r))) & sign) != 0 if code in (5, 6, 7, 8, 9) else (bool(original & value & sign) if code == 14 else False)
            self.reg[2] = (self.reg[2] & ~0x107) | int(carry) | (2 if r == 0 else 0) | (4 if r & sign else 0) | (0x100 if overflow else 0)
        if code not in (9, 11):
            if address is None:
                self.reg[dst] = result & mask
            elif byte:
                self.write8(address, result)
            else:
                self.write16(address, result)
