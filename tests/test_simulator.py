import time
import unittest
import tkinter as tk

from simulator import Simulator


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.sim = Simulator(self.root)

    def tearDown(self):
        self.sim.close()

    def wait_for(self, predicate, seconds=8):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.root.update()
            if predicate():
                return
            time.sleep(0.01)
        self.fail('Timed out: ' + self.sim.log.get('1.0', 'end'))

    def test_instructor_example_compiles_and_runs(self):
        self.sim.run()
        self.wait_for(lambda: self.sim.memory is not None)
        self.wait_for(lambda: self.sim.memory[0] & 1)
        self.assertIsNone(self.sim.process.poll())

    def test_button_controls_green_output(self):
        self.sim.editor.delete('1.0', 'end')
        self.sim.editor.insert('1.0', '''#include <msp430.h>
int main(void) {
    P4DIR |= BIT7;
    P2DIR &= ~BIT1;
    P2REN |= BIT1;
    P2OUT |= BIT1;
    while (1) {
        if (P2IN & BIT1) P4OUT &= ~BIT7;
        else P4OUT |= BIT7;
    }
}
''')
        self.sim.run()
        self.wait_for(lambda: self.sim.memory is not None and self.sim.memory[8] & 128)
        self.sim.press()
        self.wait_for(lambda: self.sim.memory[9] & 128)
        self.sim.release()
        self.wait_for(lambda: not (self.sim.memory[9] & 128))

    def test_second_button_input(self):
        self.sim.run()
        self.wait_for(lambda: self.sim.memory is not None)
        self.assertTrue(self.sim.memory[2] & 2)
        self.sim.press_s2()
        self.assertFalse(self.sim.memory[2] & 2)
        self.sim.release_s2()
        self.assertTrue(self.sim.memory[2] & 2)

    def test_gpio_input_override_and_resistor(self):
        self.sim.run()
        self.wait_for(lambda: self.sim.memory is not None)
        self.sim.pin_choice.set('P2.3')
        self.sim.set_input(1)
        self.assertTrue(self.sim.memory[6] & 8)
        self.sim.set_input(0)
        self.assertFalse(self.sim.memory[6] & 8)
        self.sim.memory[7] |= 8
        self.sim.memory[5] |= 8
        self.sim.set_input(None)
        self.assertTrue(self.sim.memory[6] & 8)
        self.sim.memory[5] &= ~8
        self.sim.update_inputs()
        self.assertFalse(self.sim.memory[6] & 8)

    def test_compile_error_is_reported(self):
        self.sim.editor.delete('1.0', 'end')
        self.sim.editor.insert('1.0', '#include <msp430.h>\nint main(void) { UNKNOWN_REGISTER = 1; }')
        self.sim.run()
        self.wait_for(lambda: not self.sim.building)
        self.assertIn('UNKNOWN_REGISTER', self.sim.log.get('1.0', 'end'))
        self.assertEqual(self.sim.status.get(), 'Build failed')


if __name__ == '__main__':
    unittest.main()
