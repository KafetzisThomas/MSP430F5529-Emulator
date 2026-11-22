# MSP430F5529 GPIO teaching simulator

A Windows desktop teaching simulator for exploring simple MSP430F5529 C firmware, GPIO, LEDs, and buttons. It compiles firmware with TI's MSP430 GCC and runs it on an **experimental, incomplete CPU emulator**; it is not a substitute for testing on hardware.

## What you can explore

- Edit C in a Dear ImGui window, compile it, and inspect approximate P1, P2, and P4 GPIO state on a schematic board.
- Exercise active-low S1 (P2.1) and S2 (P1.1), and set input overrides for other pins.
- Execute a subset of MSP430 instructions, with optional native batching and a Python fallback. A partial unsigned 16-bit multiplier is mapped.
- Use the legacy Tkinter host-C simulator separately; it is not the firmware emulator.

See [feature coverage](FEATURE_COVERAGE.md) for the acceptance baseline and unsupported scenarios. **Only run trusted source:** firmware execution is not a security boundary, and the legacy simulator executes compiled native code without a sandbox.

## Quick start (Windows)

The commands below use **Command Prompt** from the project root. Windows is the environment exercised by this project; other platforms are not established. You need Python with Tkinter, `pip`, and access to a graphical desktop. The current environment ran the tests with Python 3.14.2 and `imgui-bundle` 1.93.0; other Python versions have not been verified here.

1. Install the Python dependency:

   ```cmd
   python -m pip install -r requirements.txt
   ```

2. Obtain TI's Windows MSP430 GCC toolchain and MSP430 GCC support files separately. They are not included in a fresh checkout. The code expects these exact paths:

   ```text
   %LOCALAPPDATA%\MSP430SimToolchain\bin\msp430-elf-gcc.exe
   %LOCALAPPDATA%\MSP430SimSupport\include\msp430f5529.h
   ```

   The support `include` directory must also contain the appropriate device linker files. The original local setup uses the `msp430-gcc-9.3.1.11_win64` and `msp430-gcc-support-files` directories and directory junctions to avoid toolchain installation paths containing spaces. If those directories are placed at the project root and the two destinations above **do not already exist**, create the junctions from Command Prompt:

   ```cmd
   mklink /J "%LOCALAPPDATA%\MSP430SimToolchain" "%CD%\msp430-gcc-9.3.1.11_win64"
   mklink /J "%LOCALAPPDATA%\MSP430SimSupport" "%CD%\msp430-gcc-support-files"
   ```

   Adjust the targets to the actual extracted directories if necessary. Do not overwrite existing paths; inspect them first. Moving a target or changing Windows accounts requires updating the corresponding setup.

3. Launch the application:

   ```cmd
   python simulator_imgui.py
   ```

   Alternatively, double-click `run.bat`. The editor opens with a built-in blink example. Click **Run firmware**; a successful build changes the status to running and the P1.0 LED should blink. Build and execution errors appear in **Build output**.

For a second exercise, open [button_toggle.c](examples/button_toggle.c), click **Run firmware**, and press S1: the red P1.0 LED toggles on each debounced press. These are polling examples, not interrupt demonstrations.

A host `gcc` on PATH, matching Python's architecture, is optional for native instruction batching; it is separate from TI's cross-compiler. If building or loading the native backend fails, the firmware runner uses the Python fallback. The status identifies the active mode.

## Scope and limitations

- This is not a complete MSP430X CPU. Unsupported instructions stop execution; some unsupported hardware register writes may instead be stored without hardware effects.
- GPIO and button behavior are approximations updated in batches. Floating inputs default low unless a pull resistor or override is selected; electrical contention is not modeled.
- Watchdog, clock control, interrupts, timers, serial, ADC, USB, low-power modes, and most peripherals are not simulated. Unmapped memory is RAM-like, not an enforced F5529 memory map. The multiplier supports immediate 16-bit unsigned word multiplication only.
- The worker uses experimental cycle counts and an adjustable assumed MCLK, defaulting to 1,048,576 Hz. Wall-clock speed varies, and the GUI warns when it falls behind. Do not rely on timing, frequency, power, or hardware correctness.
- The board illustration is schematic, not a precise hardware representation. See [feature coverage](FEATURE_COVERAGE.md) for details.

## Architecture and development

Example firmware lives in `examples/`; automated tests and their ELF/source fixtures live in `tests/`. Application modules, the host compatibility header, and the Windows launcher remain at the project root.

The GUI compiles source into ELF, loads it into the CPU, and runs batches on a worker; GPIO state is synchronized with the board model. [Architecture](docs/ARCHITECTURE.md) contains a source-linked diagram and boundaries. [Contributing](CONTRIBUTING.md) describes the test and development workflow.

From the project root, run the full suite with:

```cmd
python -m unittest discover -v
```

The full suite requires the configured MSP430 toolchain and support files, a host `gcc`, the Python dependency, and a usable GUI display; some native-batch tests skip if the backend is unavailable. A smaller CPU-memory/peripheral check does not require compilers or a display:

```cmd
python -m unittest -v tests.test_memory tests.test_multiplier
```

`python benchmark_cpu.py` is an optional local benchmark requiring the configured firmware toolchain and native backend; its measurements are machine-dependent and do not establish hardware timing accuracy.

## Troubleshooting

- **Compiler cannot start:** check the exact `%LOCALAPPDATA%` paths above, junction targets, and that the Windows compiler executable exists.
- **Build fails:** inspect **Build output**, verify the device support headers and linker files, and check your C source.
- **CPU stops:** the firmware may use an unimplemented instruction or peripheral operation; consult the build output and [coverage](FEATURE_COVERAGE.md).
- **Slow execution / Python fallback:** check host `gcc` and matching architecture; even native batching does not guarantee real-time operation.
- **GUI fails to start:** verify Tkinter and `imgui-bundle` are installed for the Python interpreter being used and that a graphical session is available.

## References and license

The implementation refers to TI's MSP430x5xx/x6xx family guide (SLAU208Q), MSP430F5529 device datasheet (SLAS590P), and TI MSP430 GCC device support files. Local reference copies and downloaded toolchains are ignored by Git and are not distributed here.

This project is **source-available**, not open source under the Open Source Definition: the custom [license](LICENSE) permits noncommercial use and requires source code to be provided to recipients of modified versions. Commercial use requires prior permission from the relevant copyright holders. Third-party components retain their own terms. See the full license for details.
