import unittest
from pathlib import Path

from msp430_cpu import CPU
from msp430_memory import Memory


class RecordingPeripheral:
    def __init__(self):
        self.events = []
        self.value = 0x1234

    def read(self, address, width):
        self.events.append(('read', address, width))
        return self.value

    def write(self, address, width, value):
        self.events.append(('write', address, width, value))
        self.value = value


class MemoryTests(unittest.TestCase):
    def test_little_endian_and_bounds(self):
        memory = Memory()
        memory.write(0x2400, 2, 0x1234)
        self.assertEqual(memory.read(0x2400, 1), 0x34)
        self.assertEqual(memory.read(0x2400, 2), 0x1234)
        with self.assertRaises(IndexError):
            memory.read(Memory.SIZE - 1, 2)
        with self.assertRaises(IndexError):
            memory.write(-1, 1, 0)

    def test_mapping_checks_and_word_is_single_operation(self):
        memory = Memory()
        device = RecordingPeripheral()
        memory.map_region(0x200, 0x201, device)
        memory.write(0x200, 2, 0xabcd)
        self.assertEqual(memory.read(0x200, 2), 0xabcd)
        self.assertEqual(device.events, [('write', 0x200, 2, 0xabcd), ('read', 0x200, 2)])
        with self.assertRaises(ValueError):
            memory.map_region(0x201, 0x202, device)
        with self.assertRaises(ValueError):
            memory.read(0x1ff, 2)

    def test_cpu_instruction_uses_mapped_register(self):
        cpu = CPU((Path(__file__).parent / 'fixtures' / 'test_firmware.elf').read_bytes())
        device = RecordingPeripheral()
        cpu.memory.map_region(0x200, 0x201, device)
        cpu.reg[0], cpu.reg[4] = 0x4400, 0xabcd
        cpu.write16(0x4400, 0x4482)  # MOV R4, &0x0200
        cpu.write16(0x4402, 0x0200)
        cpu.step()
        self.assertEqual(device.value, 0xabcd)
        self.assertEqual(device.events, [('write', 0x200, 2, 0xabcd)])


if __name__ == '__main__':
    unittest.main()
