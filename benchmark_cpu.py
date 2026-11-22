"""Run from project root: python benchmark_cpu.py (GUI not required)."""
import time
from pathlib import Path
from cpu_batch import BatchRunner
from msp430_cpu import CPU
from simulator_imgui import FirmwareModel


def main():
    elf = (Path(__file__).resolve().parent / 'tests' / 'fixtures' / 'test_firmware.elf').read_bytes()
    results = []
    for fast in (False, True):
        cpu = CPU(elf)
        runner = BatchRunner(cpu)
        if fast and not runner.native:
            raise SystemExit('Native backend unavailable; check host gcc on PATH.')
        start = time.perf_counter()
        for _ in range(500):
            if fast:
                runner.run(1000)
            else:
                for _ in range(1000):
                    cpu.step()
        elapsed = time.perf_counter() - start
        print('native' if fast else 'python', f'{cpu.cycles/elapsed:,.0f} cycles/s')
        results.append((cpu.reg, cpu.mem, cpu.instructions, cpu.cycles))
    assert results[0] == results[1], 'CPU states diverged'

    model = FirmwareModel()
    try:
        model.run((Path(__file__).resolve().parent / 'examples' / 'blink_2hz.c').read_text())
        deadline = time.monotonic() + 10
        edges = []
        previous = None
        while time.monotonic() < deadline and len(edges) < 9:
            model.tick()
            if model.cpu is not None:
                state = bool(model.memory[1] & 1)
                if previous is not None and state != previous:
                    edges.append(time.monotonic())
                previous = state
            elif not model.building:
                raise RuntimeError(model.log)
            time.sleep(0.001)
        if len(edges) != 9:
            raise RuntimeError('Timed out waiting for LED transitions: ' + model.log)
        print(model.status, f'{1000*(edges[-1]-edges[0])/8:.1f} ms/LED transition (8 intervals)')
    finally:
        model.stop()


if __name__ == '__main__':
    main()
