"""Windows host-based GPIO teaching simulator; not an MSP430 emulator."""
import mmap
import os
from pathlib import Path
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import uuid

ROOT = Path(__file__).resolve().parent
SIZE = 14
EXAMPLE = '''#include <msp430.h>

int main(void)
{
    WDTCTL = WDTPW | WDTHOLD;
    P1DIR |= BIT0;
    volatile unsigned int i;
    while (1) {
        P1OUT = BIT0;
        for (i = 10000; i > 0; i--);
        P1OUT = 0;
        for (i = 10000; i > 0; i--);
    }
}
'''


class Simulator:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.memory = None
        self.temp = None
        self.building = False
        self.pressed = False
        self.s2_pressed = False
        self.external_inputs = {}
        self.source_path = None
        self.view_job = None
        self.build_job = None
        root.title('MSP430F5529 GPIO teaching simulator')
        root.geometry('1200x800')
        root.protocol('WM_DELETE_WINDOW', self.close)

        bar = ttk.Frame(root, padding=6)
        bar.pack(fill='x')
        for text, command in [('Open', self.open_file), ('Save As', self.save_file),
                              ('Run', self.run), ('Stop', self.stop)]:
            ttk.Button(bar, text=text, command=command).pack(side='left', padx=3)
        self.status = tk.StringVar(value='Ready — only run trusted C code.')
        ttk.Label(bar, textvariable=self.status).pack(side='left', padx=12)

        content = ttk.Panedwindow(root, orient='horizontal')
        content.pack(fill='both', expand=True, padx=8)
        left = ttk.Frame(content)
        right = ttk.Frame(content, padding=12)
        content.add(left, weight=3)
        content.add(right, weight=2)
        ttk.Label(left, text='C source').pack(anchor='w')
        self.editor = scrolledtext.ScrolledText(left, wrap='none', font=('Consolas', 11), undo=True)
        self.editor.pack(fill='both', expand=True)
        self.editor.insert('1.0', EXAMPLE)

        ttk.Label(right, text='MSP430F5529 LaunchPad', font=('Segoe UI', 16, 'bold')).pack(pady=8)
        self.board = tk.Canvas(right, width=340, height=390, bg='#a31f2a', highlightthickness=0)
        self.board.pack(pady=4)
        self.board.create_rectangle(8, 8, 332, 382, outline='#f0b5b5', width=2)
        self.board.create_rectangle(35, 12, 90, 40, fill='#c0c0c0', outline='white')
        self.board.create_text(62, 26, text='USB', fill='#333')
        self.board.create_text(170, 22, text='MSP-EXP430F5529LP', fill='white', font=('Segoe UI', 9, 'bold'))
        self.board.create_rectangle(124, 50, 216, 115, fill='#272727', outline='#aaa')
        self.board.create_text(170, 82, text='DEBUGGER', fill='white')
        self.board.create_rectangle(110, 176, 230, 268, fill='#282828', outline='#aaa', width=2)
        self.board.create_text(170, 220, text='MSP430\nF5529', fill='white', font=('Segoe UI', 14, 'bold'))
        left_labels = ['3V3', 'P6.5', 'P3.4', 'P3.3', 'P1.6', 'P6.6', 'P3.2', 'P2.7', 'P4.2', 'P4.1']
        right_labels = ['GND', 'P2.0', 'P2.2', 'P7.4', 'RST', 'P3.0', 'P3.1', 'P2.6', 'P2.3', 'P8.1']
        for index, (left_pin, right_pin) in enumerate(zip(left_labels, right_labels)):
            y = 125 + index * 18
            for x in (23, 317):
                self.board.create_oval(x - 4, y - 4, x + 4, y + 4, fill='#d7b275', outline='#fff')
            self.board.create_text(33, y, text=left_pin, anchor='w', fill='white', font=('Consolas', 8))
            self.board.create_text(307, y, text=right_pin, anchor='e', fill='white', font=('Consolas', 8))
        self.board.create_text(170, 150, text='Header labels: reference only', fill='#ffe5bb', font=('Segoe UI', 8))
        self.board.create_rectangle(55, 310, 98, 345, fill='#333', outline='#aaa')
        self.board.create_rectangle(242, 310, 285, 345, fill='#333', outline='#aaa')
        self.board.create_text(76, 328, text='S1', fill='white')
        self.board.create_text(263, 328, text='S2', fill='white')
        self.red = self.board.create_oval(125, 320, 145, 340, fill='#451010', outline='white')
        self.green = self.board.create_oval(195, 320, 215, 340, fill='#103d19', outline='white')
        self.board.create_text(135, 352, text='P1.0', fill='white')
        self.board.create_text(205, 352, text='P4.7', fill='white')
        buttons = ttk.Frame(right)
        buttons.pack(pady=4)
        self.button = ttk.Button(buttons, text='Hold S1 (P2.1)')
        self.button.pack(side='left', padx=3)
        self.button.bind('<ButtonPress-1>', self.press)
        self.button.bind('<ButtonRelease-1>', self.release)
        self.button2 = ttk.Button(buttons, text='Hold S2 (P1.1)')
        self.button2.pack(side='left', padx=3)
        self.button2.bind('<ButtonPress-1>', self.press_s2)
        self.button2.bind('<ButtonRelease-1>', self.release_s2)
        root.bind('<FocusOut>', self.release_all)
        pins = ttk.Frame(right)
        pins.pack(pady=3)
        ttk.Label(pins, text='GPIO input:').pack(side='left')
        self.pin_choice = ttk.Combobox(pins, state='readonly', width=6,
            values=[f'P{port}.{bit}' for port in (1, 2, 4) for bit in range(8)
                    if (port, bit) not in ((1, 1), (2, 1))])
        self.pin_choice.current(0)
        self.pin_choice.pack(side='left', padx=3)
        for label, level in [('Low', 0), ('High', 1), ('Float', None)]:
            ttk.Button(pins, text=label, width=5,
                       command=lambda value=level: self.set_input(value)).pack(side='left', padx=1)
        self.pin_status = tk.StringVar(value='GPIO input override: none')
        ttk.Label(right, textvariable=self.pin_status).pack()
        self.regtext = tk.StringVar(value='Registers: stopped')
        ttk.Label(right, textvariable=self.regtext, font=('Consolas', 10), justify='left').pack(anchor='w', pady=8)
        ttk.Label(right, text='Host timing is NOT MSP430 timing.\nFast changes may not be visible.\nTimers and interrupts are not simulated.',
                  foreground='#9b3200', justify='left').pack(anchor='w', pady=8)
        ttk.Label(root, text='Compiler / program messages').pack(anchor='w', padx=8)
        self.log = scrolledtext.ScrolledText(root, height=7, wrap='word', font=('Consolas', 10))
        self.log.pack(fill='x', padx=8, pady=(0, 8))
        self.view_job = self.root.after(20, self.update_view)

    def message(self, text):
        self.log.insert('end', text + '\n')
        self.log.see('end')

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('C / text files', '*.c *.txt'), ('All files', '*.*')])
        if path:
            try:
                text = Path(path).read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError) as exc:
                messagebox.showerror('Open failed', str(exc))
                return
            self.editor.delete('1.0', 'end')
            self.editor.insert('1.0', text)
            self.source_path = Path(path)

    def save_file(self):
        path = filedialog.asksaveasfilename(defaultextension='.c', filetypes=[('C source', '*.c'), ('Text', '*.txt')])
        if path:
            try:
                Path(path).write_text(self.editor.get('1.0', 'end-1c'), encoding='utf-8')
                self.source_path = Path(path)
            except OSError as exc:
                messagebox.showerror('Save failed', str(exc))

    def run(self):
        if self.building:
            return
        self.stop()
        self.log.delete('1.0', 'end')
        self.temp = tempfile.TemporaryDirectory(prefix='msp430-sim-')
        work = Path(self.temp.name)
        source = work / 'program.c'
        source.write_text(self.editor.get('1.0', 'end-1c'), encoding='utf-8')
        executable = work / 'program.exe'
        try:
            self.process = subprocess.Popen(['gcc', '-std=c11', '-O0', '-I', str(ROOT), str(source), '-o', str(executable)],
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            self.message('Could not start GCC: ' + str(exc))
            self.status.set('Build failed')
            self.stop(clean_status=False)
            return
        self.building = True
        self.status.set('Compiling...')
        self.build_job = self.root.after(50, lambda: self.finish_build(executable))

    def finish_build(self, executable):
        if not self.building or self.process is None:
            return
        if self.process.poll() is None:
            self.build_job = self.root.after(50, lambda: self.finish_build(executable))
            return
        output = self.process.communicate()[0].decode('utf-8', errors='replace')
        returncode = self.process.returncode
        self.process = None
        if output:
            self.message(output.rstrip())
        if returncode != 0:
            self.message('Build failed. Unsupported device registers or syntax may be the cause.')
            self.status.set('Build failed')
            self.building = False
            self.stop(clean_status=False)
            return
        self.process = None
        self.building = False
        name = 'Local\\MSP430Sim_' + uuid.uuid4().hex
        self.memory = mmap.mmap(-1, SIZE, tagname=name)
        self.memory[:] = bytes(SIZE)
        self.memory[2] = 0x02  # Released S2, assumed pulled high.
        self.memory[6] = 0x02  # Released S1, assumed pulled high.
        environment = os.environ.copy()
        environment['MSP430_SIM_MAPPING'] = name
        try:
            self.process = subprocess.Popen([str(executable)], env=environment,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            self.message('Could not run program: ' + str(exc))
            self.status.set('Run failed')
            self.stop(clean_status=False)
            return
        self.message('Compiled for Windows; this is not MSP430 firmware. Run trusted programs only.')
        self.status.set('Running (host timing)')

    def press(self, event=None):
        self.pressed = True
        self.apply_button()

    def release(self, event=None):
        self.pressed = False
        self.apply_button()

    def press_s2(self, event=None):
        self.s2_pressed = True
        self.apply_button()

    def release_s2(self, event=None):
        self.s2_pressed = False
        self.apply_button()

    def release_all(self, event=None):
        self.pressed = False
        self.s2_pressed = False
        self.apply_button()

    def apply_button(self):
        if self.memory:
            # Both switches are active low; released inputs are assumed high.
            self.memory[6] = (self.memory[6] & ~2) if self.pressed else (self.memory[6] | 2)
            self.memory[2] = (self.memory[2] & ~2) if self.s2_pressed else (self.memory[2] | 2)

    def set_input(self, level):
        pin = self.pin_choice.get()
        if level is None:
            self.external_inputs.pop(pin, None)
        else:
            self.external_inputs[pin] = level
        self.pin_status.set('GPIO overrides: ' + (', '.join(
            f'{name}={value}' for name, value in sorted(self.external_inputs.items())) or 'none'))
        self.update_inputs()

    def update_inputs(self):
        if not self.memory:
            return
        # A periodic teaching approximation, not cycle-accurate electrical simulation.
        for port, offset in ((1, 0), (2, 4), (4, 8)):
            direction, output, inputs, resistor = self.memory[offset:offset + 4]
            for bit in range(8):
                mask = 1 << bit
                if (port, bit) in ((1, 1), (2, 1)):
                    continue
                level = self.external_inputs.get(f'P{port}.{bit}')
                if direction & mask:
                    level = bool(output & mask)
                elif level is None:
                    level = bool(output & mask) if resistor & mask else False
                inputs = inputs | mask if level else inputs & ~mask
            self.memory[offset + 2] = inputs

    def update_view(self):
        if self.memory:
            self.update_inputs()
            r = self.memory[:]
            red = bool(r[0] & r[1] & 1)
            green = bool(r[8] & r[9] & 128)
            self.board.itemconfig(self.red, fill='#ff2424' if red else '#451010')
            self.board.itemconfig(self.green, fill='#33ff55' if green else '#103d19')
            self.regtext.set('      DIR OUT  IN REN\nP1    %02X  %02X  %02X  %02X\nP2    %02X  %02X  %02X  %02X\nP4    %02X  %02X  %02X  %02X' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11]))
        if self.process and not self.building and self.process.poll() is not None:
            code = self.process.returncode
            self.message('Program exited with code %s.' % code)
            self.status.set('Program exited')
            self.stop(clean_status=False)
        self.view_job = self.root.after(20, self.update_view)

    def stop(self, clean_status=True):
        self.building = False
        if self.build_job:
            self.root.after_cancel(self.build_job)
            self.build_job = None
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.communicate(timeout=5)
            self.process = None
        if self.memory:
            self.memory.close()
            self.memory = None
        if self.temp:
            self.temp.cleanup()
            self.temp = None
        self.pressed = False
        self.s2_pressed = False
        self.board.itemconfig(self.red, fill='#451010')
        self.board.itemconfig(self.green, fill='#103d19')
        self.regtext.set('Registers: stopped')
        if clean_status:
            self.status.set('Stopped')

    def close(self):
        self.stop()
        if self.view_job:
            self.root.after_cancel(self.view_job)
        self.root.destroy()


if __name__ == '__main__':
    Simulator(tk.Tk()).root.mainloop()
