import time
import unittest

from imgui_bundle import hello_imgui
from simulator_imgui import App, Model, FirmwareModel, ROOT, EXAMPLE


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.model = Model()

    def tearDown(self):
        self.model.stop()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            self.model.tick()
            if predicate():
                return
            time.sleep(0.01)
        self.fail('Timed out: ' + self.model.log)

    def test_compile_run_gpio_and_buttons(self):
        self.model.run(EXAMPLE)
        self.wait_for(lambda: self.model.memory is not None and self.model.memory[0] & 1)
        self.assertTrue(self.model.memory[6] & 2)
        self.model.s1 = True
        self.model.tick()
        self.assertFalse(self.model.memory[6] & 2)
        self.model.s1 = False
        self.model.s2 = True
        self.model.overrides[(2, 3)] = 1
        self.model.tick()
        self.assertFalse(self.model.memory[2] & 2)
        self.assertTrue(self.model.memory[6] & 8)
        self.model.overrides.clear()
        self.model.memory[7] |= 8
        self.model.memory[5] |= 8
        self.model.tick()
        self.assertTrue(self.model.memory[6] & 8)

    def test_pin_snapshot_decodes_registers(self):
        self.model.run(EXAMPLE)
        self.wait_for(lambda: self.model.memory is not None)
        self.model.memory[4] &= ~8
        self.model.memory[7] |= 8
        self.model.memory[5] |= 8
        self.model.update_inputs()
        self.assertEqual(self.model.pin_snapshot(2, 3),
                         {'direction': 'input', 'out': True, 'in': True, 'resistor': 'pull-up'})
        self.model.memory[5] &= ~8
        self.model.update_inputs()
        self.assertEqual(self.model.pin_snapshot(2, 3)['resistor'], 'pull-down')
        self.model.memory[4] |= 8
        self.assertEqual(self.model.pin_snapshot(2, 3)['direction'], 'output')
        self.assertEqual(self.model.pin_snapshot(2, 3)['resistor'], 'disabled')

    def test_compile_error(self):
        self.model.run('#include <msp430.h>\nint main(void) { UNKNOWN_REGISTER = 1; }')
        self.wait_for(lambda: not self.model.building)
        self.assertEqual(self.model.status, 'Build failed')
        self.assertIn('UNKNOWN_REGISTER', self.model.log)

    def test_firmware_button_latches_red_led(self):
        self.model = FirmwareModel()
        m = self.model
        m.run((ROOT / 'button_toggle.c').read_text())
        self.wait_for(lambda: m.cpu is not None and m.memory[7] & 2)

        def observe(pressed, expected):
            m.s1 = pressed
            # Allow for batched input sampling and firmware debounce.
            start = m.cpu.cycles
            self.wait_for(lambda: m.cpu.cycles - start >= 40000)
            self.assertEqual(bool(m.memory[6] & 2), not pressed)
            self.assertEqual(bool(m.memory[0] & m.memory[1] & 1), expected)

        observe(False, False)
        m.s2 = True
        observe(False, False)  # P1.1 must not act like P2.1.
        m.s2 = False
        observe(True, True)
        observe(True, True)
        observe(False, True)
        observe(True, False)
        observe(False, False)

    def test_imgui_frame(self):
        app = App()
        params = hello_imgui.RunnerParams()
        params.app_window_params.window_title = 'ImGui smoke test'
        from board_ui import style_workbench
        params.callbacks.setup_imgui_style = style_workbench
        def render():
            app.render()
            params.app_shall_exit = True
        params.callbacks.show_gui = render
        try:
            hello_imgui.run(params)
        finally:
            app.model.stop()


if __name__ == '__main__':
    unittest.main()
