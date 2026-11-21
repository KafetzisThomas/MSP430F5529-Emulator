import unittest
from pathlib import Path

from msp430_cpu import CPU


class MultiplierTests(unittest.TestCase):
    def setUp(self):
        self.cpu = CPU(Path('test_firmware.elf').read_bytes())

    def test_unsigned_product_and_repeated_operand(self):
        cpu = self.cpu
        cpu.write16(0x4c0, 0xffff)
        cpu.write16(0x4c8, 0x1234)
        self.assertEqual(cpu.read16(0x4ca), 0xedcc)
        self.assertEqual(cpu.read16(0x4cc), 0x1233)
        self.assertEqual(cpu.read16(0x4ce), 0)
        self.assertEqual(cpu.read8(0x4cb), 0xed)
        cpu.write16(0x4c8, 2)
        self.assertEqual(cpu.read16(0x4ca), 0xfffe)
        self.assertEqual(cpu.read16(0x4cc), 1)

    def test_instructions_use_multiplier_registers(self):
        cpu = self.cpu
        cpu.reg[0], cpu.reg[4], cpu.reg[5] = 0x4400, 0x1234, 3
        for address, word in ((0x4400, 0x4482), (0x4402, 0x4c0),
                              (0x4404, 0x4582), (0x4406, 0x4c8),
                              (0x4408, 0x4216), (0x440a, 0x4ca)):
            cpu.write16(address, word)
        for _ in range(3):
            cpu.step()
        self.assertEqual(cpu.reg[6], 0x369c)

    def test_unsupported_modes_are_not_silently_simulated(self):
        with self.assertRaises(ValueError):
            self.cpu.write16(0x4c2, 1)
        with self.assertRaises(ValueError):
            self.cpu.write8(0x4c0, 1)


if __name__ == '__main__':
    unittest.main()
