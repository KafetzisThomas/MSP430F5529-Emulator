import unittest
from pathlib import Path
from msp430_cpu import CPU, UnsupportedInstruction
from simulator_imgui import FirmwareModel, EXAMPLE
import time


class CpuTests(unittest.TestCase):
    def test_real_compiled_blink(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        saw_on = False
        saw_off_after_on = False
        for _ in range(160000):
            cpu.step()
            if cpu.mem[0x204] & 1:
                if cpu.mem[0x202] & 1:
                    saw_on = True
                elif saw_on:
                    saw_off_after_on = True
                    break
        self.assertTrue(saw_on and saw_off_after_on)

    def test_cycle_counts_for_blink_instructions(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        expected = [(0x4400, 2), (0x4404, 1), (0x4406, 4),
                    (0x440a, 1), (0x440c, 4), (0x4412, 3),
                    (0x4416, 1), (0x4418, 2), (0x441c, 3),
                    (0x4420, 3), (0x4424, 1), (0x4426, 2),
                    (0x442a, 3), (0x442e, 4), (0x4434, 2),
                    (0x443e, 2), (0x4440, 1), (0x4442, 2),
                    (0x4436, 2), (0x4438, 1), (0x443a, 3)]
        for pc, cycles in expected:
            self.assertEqual(cpu.reg[0], pc)
            previous = cpu.cycles
            cpu.step()
            self.assertEqual(cpu.cycles - previous, cycles, hex(pc))

    def test_blink_transition_cycle_count(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        start = None
        for _ in range(200000):
            old = cpu.mem[0x202] & 1
            cpu.step()
            new = cpu.mem[0x202] & 1
            if not old and new:
                start = cpu.cycles
            elif old and not new and start is not None:
                # Setup 4+2+5, 10,000 loop iterations at 11 cycles,
                # then branch 2 and next GPIO toggle 3+1+2+3.
                self.assertEqual(cpu.cycles - start, 110022)
                return
        self.fail('LED did not complete a high interval')

    def test_firmware_model_compiles_and_blinks(self):
        model = FirmwareModel()
        try:
            model.run(EXAMPLE)
            deadline = time.monotonic() + 20
            saw_on = False
            saw_off = False
            while time.monotonic() < deadline:
                model.tick()
                if model.cpu:
                    if model.memory[1] & 1:
                        saw_on = True
                    elif saw_on:
                        saw_off = True
                        break
                elif not model.building:
                    self.fail(model.status + ': ' + model.log)
                time.sleep(0.001)
            self.assertTrue(saw_on and saw_off, model.log)
        finally:
            model.stop()

    def test_cpu_progresses_without_gui_ticks(self):
        model = FirmwareModel()
        try:
            model.run(EXAMPLE)
            deadline = time.monotonic() + 20
            while model.cpu is None and time.monotonic() < deadline:
                model.tick()
                time.sleep(0.01)
            self.assertIsNotNone(model.cpu, model.log)
            time.sleep(0.15)
            start = model.cpu.instructions
            time.sleep(0.25)  # No tick or render calls during this interval.
            idle_progress = model.cpu.instructions - start
            start = model.cpu.instructions
            end = time.monotonic() + 0.25
            while time.monotonic() < end:
                model.tick()
                time.sleep(0.005)
            active_progress = model.cpu.instructions - start
            self.assertGreater(idle_progress, 10000)
            self.assertGreater(active_progress, 10000)
            self.assertLess(max(idle_progress, active_progress) / min(idle_progress, active_progress), 2)
        finally:
            model.stop()

    def test_extended_classic_double_operand_instructions(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        # Register-direct R4 -> R5, word and byte variants.
        cases = [
            (0x6405, 0xffff, 0, 1, 0, 0x003),  # ADDC: carry and zero
            (0x6445, 0x7f, 0, 1, 0x80, 0x104),  # ADDC.B: signed overflow
            (0x7405, 0, 0, 0, 0xffff, 0x004),  # SUBC: borrow
            (0x7445, 1, 0x80, 1, 0x7f, 0x101),  # SUBC.B: signed overflow
            (0xb405, 0x0f, 0xf0, 0x101, 0xf0, 0x002),  # BIT: no write
            (0xc405, 0x0f, 0xff, 0x105, 0xf0, 0x105),  # BIC: flags unchanged
        ]
        for opcode, src, dst, sr, expected, flags in cases:
            with self.subTest(opcode=hex(opcode)):
                cpu.reg[0], cpu.reg[4], cpu.reg[5], cpu.reg[2] = 0x4400, src, dst, sr
                cpu.write16(0x4400, opcode)
                cpu.step()
                self.assertEqual(cpu.reg[5], expected)
                self.assertEqual(cpu.reg[2] & 0x107, flags)

    def test_single_operand_register_operations(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        cases = [
            (0x1004, 0x0001, 0x101, 0x8000, 0x005),
            (0x1044, 0x0002, 0, 0x0001, 0),
            (0x1104, 0x8001, 0x100, 0xc000, 0x005),
            (0x1084, 0x1234, 0x105, 0x3412, 0x105),
            (0x1184, 0x0080, 0, 0xfff80, 0x005),
            (0x1184, 0x0000, 0x101, 0, 0x002),
        ]
        for opcode, value, flags, expected, expected_flags in cases:
            with self.subTest(opcode=hex(opcode), value=value):
                cpu.reg[0], cpu.reg[4], cpu.reg[2] = 0x4400, value, flags
                cpu.write16(0x4400, opcode)
                before = cpu.cycles
                cpu.step()
                self.assertEqual(cpu.reg[4], expected)
                self.assertEqual(cpu.reg[2] & 0x107, expected_flags)
                self.assertEqual(cpu.cycles - before, 1)

    def test_push_register_byte_preserves_stack_high_byte(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        cpu.reg[0], cpu.reg[1], cpu.reg[4] = 0x4400, 0x2402, 0x1234
        cpu.write16(0x2400, 0xabcd)
        cpu.write16(0x4400, 0x1244)  # PUSH.B R4
        cpu.step()
        self.assertEqual(cpu.reg[1], 0x2400)
        self.assertEqual(cpu.read16(0x2400), 0xab34)
        self.assertEqual(cpu.cycles, 3)

    def test_single_operand_memory_and_call_register(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        cpu.reg[0], cpu.reg[4], cpu.reg[2] = 0x4400, 0x2400, 1
        cpu.write16(0x2400, 0x0001)
        cpu.write16(0x4400, 0x1024)  # RRC @R4
        cpu.step()
        self.assertEqual(cpu.read16(0x2400), 0x8000)
        self.assertEqual(cpu.reg[2] & 0x107, 5)
        self.assertEqual(cpu.cycles, 3)
        cpu.write16(0x4402, 0x1194)  # SXT 2(R4)
        cpu.write16(0x4404, 2)
        cpu.write16(0x2402, 0x0080)
        cpu.step()
        self.assertEqual(cpu.read16(0x2402), 0xff80)
        self.assertEqual(cpu.cycles, 7)
        cpu.reg[1], cpu.reg[5] = 0x2500, 0x4500
        cpu.write16(0x4406, 0x1285)  # CALL R5
        cpu.step()
        self.assertEqual(cpu.reg[0], 0x4500)
        self.assertEqual(cpu.read16(0x24fe), 0x4408)
        self.assertEqual(cpu.cycles, 11)

    def test_decimal_add(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        cases = [
            (0xa405, 0x0001, 0x9999, 0, 0x0000, 0x003),
            (0xa405, 0x1234, 0x4321, 1, 0x5556, 0x000),
            (0xa445, 0x0001, 0x0078, 1, 0x0080, 0x004),
            (0xa445, 0x0050, 0x0050, 0, 0x0000, 0x003),
        ]
        for opcode, src, dst, carry, expected, flags in cases:
            with self.subTest(opcode=hex(opcode), src=src, dst=dst):
                cpu.reg[0], cpu.reg[4], cpu.reg[5], cpu.reg[2] = 0x4400, src, dst, carry | 0x100
                cpu.write16(0x4400, opcode)
                cpu.step()
                self.assertEqual(cpu.reg[5], expected)
                self.assertEqual(cpu.reg[2] & 7, flags)
                self.assertEqual(cpu.reg[2] & 0x100, 0x100)

    def test_bit_memory_does_not_write_and_uses_read_timing(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        cpu.reg[0], cpu.reg[4] = 0x4400, 1
        cpu.write16(0x4400, 0xb482)  # BIT R4, &0x2400
        cpu.write16(0x4402, 0x2400)
        cpu.write16(0x2400, 0x1234)
        cpu.step()
        self.assertEqual(cpu.read16(0x2400), 0x1234)
        self.assertEqual(cpu.reg[2] & 0x107, 2)
        self.assertEqual(cpu.cycles, 3)

    def test_unsupported_raises(self):
        cpu = CPU(Path('test_firmware.elf').read_bytes())
        cpu.mem[0x4400:0x4402] = b'\x00\x00'
        with self.assertRaises(UnsupportedInstruction):
            cpu.step()


if __name__ == '__main__':
    unittest.main()
