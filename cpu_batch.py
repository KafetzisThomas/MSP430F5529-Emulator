"""Optional native instruction batching; the Python CPU remains the reference."""
import ctypes as C
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


@lru_cache(maxsize=1)
def backend():
    source = Path(__file__).with_suffix('.c')
    try:
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        cache = source.parent / '__pycache__'
        cache.mkdir(exist_ok=True)
        target = cache / f'cpu_batch_{C.sizeof(C.c_void_p)}_{digest}.dll'
        if not target.is_file():
            with tempfile.TemporaryDirectory(dir=cache) as tmp:
                output = Path(tmp) / target.name
                subprocess.run(['gcc', '-std=c11', '-O2', '-shared', '-fPIC', str(source), '-o', str(output)],
                               capture_output=True, check=True, timeout=30)
                if not target.exists():
                    os.replace(output, target)
        run = C.CDLL(str(target)).run_batch
        u8, u32 = C.POINTER(C.c_uint8), C.POINTER(C.c_uint32)
        run.argtypes = [u8, u8, u32, C.c_uint, u32]
        run.restype = C.c_uint
        return run
    except (OSError, subprocess.SubprocessError):
        return None


class BatchRunner:
    def __init__(self, cpu):
        self.cpu = cpu
        self.native = backend()
        if self.native:
            self.data = (C.c_uint8 * len(cpu.mem)).from_buffer(cpu.mem)
            self.pages = (C.c_uint8 * 256).from_buffer(cpu.memory.mapped_low_pages)
            self.reg = (C.c_uint32 * 16)()
            self.cycles = C.c_uint32()

    def run(self, count):
        cpu = self.cpu
        if not self.native:
            for _ in range(count):
                cpu.step()
            return
        while count:
            self.reg[:] = cpu.reg
            done = self.native(self.data, self.pages, self.reg, count, C.byref(self.cycles))
            if done:
                cpu.reg[:] = self.reg
                cpu.instructions += done
                cpu.cycles += self.cycles.value
                count -= done
            if count:  # Native stopped before an unhandled instruction or peripheral.
                cpu.step()
                count -= 1
