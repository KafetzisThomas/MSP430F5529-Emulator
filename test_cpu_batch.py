import random
import unittest
from pathlib import Path
from cpu_batch import BatchRunner, backend
from msp430_cpu import CPU
from test_memory import RecordingPeripheral


@unittest.skipUnless(backend(), 'native host compiler/backend unavailable')
class BatchTests(unittest.TestCase):
    def setUp(self):
        elf = Path('test_firmware.elf').read_bytes()
        self.ref, self.fast = CPU(elf), CPU(elf)
        self.runner = BatchRunner(self.fast)

    def compare(self, count):
        for _ in range(count):
            self.ref.step()
        self.runner.run(count)
        self.assertEqual(self.ref.reg, self.fast.reg)
        self.assertEqual(self.ref.cycles, self.fast.cycles)
        self.assertEqual(self.ref.instructions, self.fast.instructions)
        self.assertEqual(self.ref.mem, self.fast.mem)

    def test_compiled_blink_across_gpio_transitions(self):
        states = set()
        for _ in range(70):
            self.compare(1000)
            states.add(self.fast.mem[0x202] & 1)
        self.assertEqual(states, {0, 1})

    def test_general_word_and_byte_alu(self):
        rng = random.Random(430)
        for code in range(4, 16):
            for byte in (0, 0x40):
                for value in (0, 1, 0x80, 0x8000, 0xffff, rng.randrange(65536)):
                    regs = [0] * 16
                    regs[0], regs[2], regs[4], regs[5] = 0x4400, rng.randrange(512), value, rng.randrange(65536)
                    for cpu in (self.ref, self.fast):
                        cpu.reg[:] = regs
                        cpu.write16(0x4400, code << 12 | 0x405 | byte)
                    self.compare(1)

    def test_late_mapping_falls_back_after_native_prefix(self):
        devices = []
        for cpu in (self.ref, self.fast):
            dev = RecordingPeripheral()
            devices.append(dev)
            cpu.memory.map_region(0x200, 0x201, dev)
            cpu.reg[0] = 0x4400
            for i, word in enumerate([0x4314, 0x4482, 0x0200, 0x5314]):
                cpu.write16(0x4400 + 2*i, word)
        self.compare(3)
        for dev in devices:
            self.assertEqual(dev.events, [('write', 0x200, 2, 1)])
