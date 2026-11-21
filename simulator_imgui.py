"""Dear ImGui front end for the host-based MSP430 GPIO teaching model."""
import mmap
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog
import uuid

from imgui_bundle import imgui, hello_imgui
from msp430_cpu import CPU, UnsupportedInstruction

ROOT = Path(__file__).resolve().parent
EXAMPLE = '''#include <msp430.h>

int main(void)
{
    WDTCTL = WDTPW | WDTHOLD;
    P1DIR |= BIT0;
    volatile unsigned int i;
    while (1) {
        P1OUT ^= BIT0;
        for (i = 10000; i > 0; i--);
    }
}
'''


class Model:
    def __init__(self):
        self.process = None
        self.memory = None
        self.temp = None
        self.building = False
        self.build_output = None
        self.status = 'Ready'
        self.log = ''
        self.overrides = {}
        self.s1 = False
        self.s2 = False

    def run(self, source):
        self.stop()
        self.log = ''
        self.temp = tempfile.TemporaryDirectory(prefix='msp430-sim-')
        path = Path(self.temp.name)
        (path / 'program.c').write_text(source, encoding='utf-8')
        self.build_output = open(path / 'compiler.log', 'w+b')
        try:
            self.process = subprocess.Popen(
                ['gcc', '-std=c11', '-O0', '-I', str(ROOT), str(path / 'program.c'),
                 '-o', str(path / 'program.exe')], stdout=self.build_output,
                stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            self.log = f'Could not start compiler: {exc}'
            self.stop()
            self.status = 'Build failed'
            return
        self.building = True
        self.status = 'Compiling'

    def tick(self):
        if self.building and self.process and self.process.poll() is not None:
            result = self.process.returncode
            self.process = None
            self.building = False
            self.build_output.seek(0)
            self.log = self.build_output.read().decode('utf-8', errors='replace')
            self.build_output.close()
            self.build_output = None
            if result:
                self.stop()
                self.status = 'Build failed'
                return
            name = 'Local\\MSP430Sim_' + uuid.uuid4().hex
            self.memory = mmap.mmap(-1, 14, tagname=name)
            self.memory[:] = bytes(14)
            self.memory[2] = self.memory[6] = 2
            env = os.environ.copy()
            env['MSP430_SIM_MAPPING'] = name
            try:
                self.process = subprocess.Popen([str(Path(self.temp.name) / 'program.exe')],
                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            except OSError as exc:
                self.log += f'\nCould not run program: {exc}'
                self.stop()
                self.status = 'Run failed'
                return
            self.status = 'Running (host timing)'
        if self.memory:
            self.update_inputs()
        if self.process and not self.building and self.process.poll() is not None:
            code = self.process.returncode
            self.stop()
            self.status = f'Program exited ({code})'

    def update_inputs(self):
        if not self.memory:
            return
        for port, offset in ((1, 0), (2, 4), (4, 8)):
            direction, output, inputs, resistor = self.memory[offset:offset + 4]
            for bit in range(8):
                mask = 1 << bit
                if (port, bit) == (1, 1):
                    level = not self.s2
                elif (port, bit) == (2, 1):
                    level = not self.s1
                elif direction & mask:
                    level = bool(output & mask)
                else:
                    level = self.overrides.get((port, bit))
                    if level is None:
                        level = bool(output & mask) if resistor & mask else False
                inputs = inputs | mask if level else inputs & ~mask
            self.memory[offset + 2] = inputs

    def pin_snapshot(self, port, bit):
        """Return sampled GPIO configuration, not a cycle-accurate pin state."""
        if self.memory is None:
            return None
        offset = {1: 0, 2: 4, 4: 8}[port]
        direction, output, inputs, resistor = self.memory[offset:offset + 4]
        mask = 1 << bit
        is_output = bool(direction & mask)
        return {
            'direction': 'output' if is_output else 'input',
            'out': bool(output & mask),
            'in': bool(inputs & mask),
            'resistor': ('disabled' if is_output or not resistor & mask
                         else 'pull-up' if output & mask else 'pull-down'),
        }

    def stop(self):
        self.building = False
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
        if self.build_output:
            self.build_output.close()
            self.build_output = None
        if self.memory:
            self.memory.close()
            self.memory = None
        if self.temp:
            self.temp.cleanup()
            self.temp = None
        self.s1 = self.s2 = False
        self.status = 'Stopped'


class FirmwareModel(Model):
    """Experimental F5529 firmware runner with a deliberately limited CPU."""
    def __init__(self):
        super().__init__()
        self.cpu = None
        self.worker = None
        self.stop_event = threading.Event()
        self.clock_hz = 1_048_576
        self.behind = False

    def run(self, source):
        self.stop()
        self.log = ''
        self.temp = tempfile.TemporaryDirectory(prefix='msp430-firmware-')
        work = Path(self.temp.name)
        (work / 'program.c').write_text(source, encoding='utf-8')
        # TI GCC's driver mishandles its own installation path when it contains spaces.
        local = Path(os.environ['LOCALAPPDATA'])
        compiler = local / 'MSP430SimToolchain' / 'bin' / 'msp430-elf-gcc.exe'
        support = local / 'MSP430SimSupport' / 'include'
        self.build_output = open(work / 'compiler.log', 'w+b')
        try:
            self.process = subprocess.Popen([str(compiler), '-mmcu=msp430f5529', '-I', str(support),
                '-L', str(support), '-O0', str(work / 'program.c'), '-o', str(work / 'program.elf')],
                stdout=self.build_output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            self.log = f'Could not start MSP430 compiler: {exc}'
            self.stop()
            self.status = 'Build failed'
            return
        self.building = True
        self.status = 'Compiling MSP430 firmware'

    def tick(self):
        if self.building and self.process and self.process.poll() is not None:
            result = self.process.returncode
            self.process = None
            self.building = False
            self.build_output.seek(0)
            self.log = self.build_output.read().decode('utf-8', errors='replace')
            self.build_output.close()
            self.build_output = None
            if result:
                self.stop()
                self.status = 'Build failed'
                return
            try:
                self.cpu = CPU((Path(self.temp.name) / 'program.elf').read_bytes())
            except (ValueError, OSError, IndexError) as exc:
                self.log += f'\nFirmware load failed: {exc}'
                self.stop()
                self.status = 'Load failed'
                return
            self.memory = bytearray(14)
            self.stop_event.clear()
            self.status = 'Running experimental MSP430 instructions'
            self.worker = threading.Thread(target=self._execute, daemon=True)
            self.worker.start()

    def _execute(self):
        # Nominal settled MCLK; instruction and clock support remain incomplete.
        batch = 1000
        self.behind = False
        deadline = time.monotonic()
        try:
            while not self.stop_event.is_set():
                start_cycles = self.cpu.cycles
                for _ in range(batch):
                    self.cpu.step()
                for offset, addresses in ((0, (0x204, 0x202, 0x200, 0x206)),
                                          (4, (0x205, 0x203, 0x201, 0x207)),
                                          (8, (0x225, 0x223, 0x221, 0x227))):
                    for index, address in enumerate(addresses):
                        self.memory[offset + index] = self.cpu.read8(address)
                self.update_inputs()
                for offset, address in ((0, 0x200), (4, 0x201), (8, 0x221)):
                    self.cpu.write8(address, self.memory[offset + 2])
                deadline += (self.cpu.cycles - start_cycles) / self.clock_hz
                now = time.monotonic()
                if deadline < now - 0.1:
                    self.behind = True
                    deadline = now
                self.stop_event.wait(max(0.0, deadline - now))
        except (UnsupportedInstruction, IndexError, ValueError) as exc:
            self.log += f'\nCPU stopped: {exc}'
            self.status = 'Unsupported CPU operation'

    def stop(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join()
            self.worker = None
        self.cpu = None
        if isinstance(self.memory, bytearray):
            self.memory = None
        super().stop()


class App:
    def __init__(self):
        self.model = FirmwareModel()
        self.source = EXAMPLE
        self.pin = 0
        self.pins = [(p, b) for p in (1, 2, 4) for b in range(8)
                     if (p, b) not in ((1, 1), (2, 1))]

    def file_dialog(self, save=False):
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        try:
            options = {'filetypes': [('C and text files', '*.c *.txt'), ('All files', '*.*')]}
            path = (filedialog.asksaveasfilename(defaultextension='.c', **options)
                    if save else filedialog.askopenfilename(**options))
        finally:
            root.destroy()
        if not path:
            return
        try:
            if save:
                Path(path).write_text(self.source, encoding='utf-8')
            else:
                self.source = Path(path).read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError) as exc:
            self.model.log = str(exc)

    def board(self):
        imgui.text('MSP-EXP430F5529LP  (schematic)')
        p = imgui.get_cursor_screen_pos()
        x, y = p.x, p.y
        draw = imgui.get_window_draw_list()
        def col(r, g, b, a=255):
            return imgui.get_color_u32(imgui.ImVec4(r/255, g/255, b/255, a/255))
        draw.add_rect_filled((x, y), (x+320, y+350), col(155, 30, 42), 8)
        draw.add_rect_filled((x+110, y+120), (x+210, y+200), col(35, 35, 35), 4)
        draw.add_text((x+127, y+145), col(255, 255, 255), 'MSP430')
        draw.add_text((x+130, y+165), col(255, 255, 255), 'F5529')
        draw.add_rect_filled((x+115, y+30), (x+205, y+80), col(35, 35, 35), 3)
        draw.add_text((x+128, y+45), col(255, 255, 255), 'DEBUGGER')
        draw.add_rect_filled((x+30, y), (x+75, y+20), col(185, 185, 185))
        for i in range(10):
            for px in (18, 302):
                draw.add_circle_filled((x+px, y+95+i*18), 4, col(230, 195, 120))
        r = self.model.memory[:] if self.model.memory else bytes(14)
        red = bool(r[0] & r[1] & 1)
        green = bool(r[8] & r[9] & 128)
        draw.add_circle_filled((x+125, y+305), 10, col(255, 30, 30) if red else col(70, 10, 10))
        draw.add_circle_filled((x+195, y+305), 10, col(20, 255, 70) if green else col(10, 60, 20))
        draw.add_text((x+105, y+322), col(255,255,255), 'P1.0')
        draw.add_text((x+177, y+322), col(255,255,255), 'P4.7')
        imgui.dummy((320, 355))
        imgui.button('Hold S1 (P2.1)', (145, 30))
        self.model.s1 = imgui.is_item_active()
        imgui.same_line()
        imgui.button('Hold S2 (P1.1)', (145, 30))
        self.model.s2 = imgui.is_item_active()
        imgui.text_disabled('Headers are decorative; GPIO selector below.')

    def render(self):
        self.model.tick()
        if imgui.button('Open'):
            self.file_dialog()
        imgui.same_line()
        if imgui.button('Save As'):
            self.file_dialog(True)
        imgui.same_line()
        if imgui.button('Run'):
            self.model.run(self.source)
        imgui.same_line()
        if imgui.button('Stop'):
            self.model.stop()
        imgui.same_line()
        imgui.text(self.model.status)
        imgui.text_colored((1.0, 0.65, 0.25, 1.0), 'Experimental MSP430 CPU subset: unsupported instructions stop execution.')
        imgui.separator()
        imgui.begin_child('editor', (imgui.get_content_region_avail().x * 0.56, 0), imgui.ChildFlags_.borders)
        imgui.text('C source')
        _, self.source = imgui.input_text_multiline('##source', self.source, (-1, -170), imgui.InputTextFlags_.allow_tab_input)
        imgui.text('Compiler messages')
        imgui.begin_child('log', (0, 120), imgui.ChildFlags_.borders)
        imgui.text_unformatted(self.model.log or 'No messages')
        imgui.end_child()
        imgui.end_child()
        imgui.same_line()
        imgui.begin_child('hardware', (0, 0), imgui.ChildFlags_.borders)
        self.board()
        labels = [f'P{p}.{b}' for p, b in self.pins]
        _, self.pin = imgui.combo('GPIO input', self.pin, labels)
        for label, level in [('Low', 0), ('High', 1), ('Float', None)]:
            if imgui.button(label):
                if level is None:
                    self.model.overrides.pop(self.pins[self.pin], None)
                else:
                    self.model.overrides[self.pins[self.pin]] = level
            imgui.same_line()
        imgui.new_line()
        imgui.text('Overrides: ' + (', '.join(f'P{p}.{b}={v}' for (p,b),v in self.model.overrides.items()) or 'none'))
        port, bit = self.pins[self.pin]
        snapshot = self.model.pin_snapshot(port, bit)
        if snapshot:
            imgui.text(f"P{port}.{bit}: {snapshot['direction']}, IN={int(snapshot['in'])}, OUT={int(snapshot['out'])}, {snapshot['resistor']}")
        else:
            imgui.text_disabled('Run a program to inspect the selected pin.')
        r = self.model.memory[:] if self.model.memory else bytes(14)
        imgui.text('      DIR OUT  IN REN')
        for port, offset in ((1, 0), (2, 4), (4, 8)):
            imgui.text(f'P{port}    ' + '  '.join(f'{value:02X}' for value in r[offset:offset+4]))
        imgui.begin_disabled(self.model.cpu is not None or self.model.building)
        changed, clock = imgui.input_int('Assumed MCLK (Hz)', self.model.clock_hz, 10000, 100000)
        if changed:
            self.model.clock_hz = max(1000, min(clock, 25000000))
        imgui.end_disabled()
        imgui.text_wrapped('Cycle timing experimental; clock changes and peripherals are not simulated.')
        if self.model.behind:
            imgui.text_colored((1.0, 0.4, 0.2, 1.0), 'Simulation cannot keep up with target clock; running slower than real time.')
        imgui.end_child()


def main():
    app = App()
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = 'MSP430F5529 GPIO teaching simulator'
    params.app_window_params.window_geometry.size = (1200, 800)
    params.fps_idling.enable_idling = False
    params.callbacks.show_gui = app.render
    try:
        hello_imgui.run(params)
    finally:
        app.model.stop()


if __name__ == '__main__':
    main()
