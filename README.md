# MSP430F5529 simulator — experimental firmware mode

Double-click `run.bat` to open the Dear ImGui interface. It compiles C using TI's Windows MSP430 GCC for `msp430f5529`, loads the ELF reset vector and executes a **limited experimental MSP430 instruction subset**. Python, Tkinter and `imgui-bundle==1.93.0` are required. Install the Python dependency with `python -m pip install -r requirements.txt`.

The compiler and support files reside in `msp430-gcc-9.3.1.11_win64` and `msp430-gcc-support-files`. On this computer, junctions `%LOCALAPPDATA%\MSP430SimToolchain` and `%LOCALAPPDATA%\MSP430SimSupport` point to those directories because the toolchain fails when its installation path contains spaces. Moving this directory or running under another account requires recreating the junctions.

## Current scope and limitations

See `FEATURE_COVERAGE.md` for the proposed firmware acceptance scenarios and their current status. CPU accesses now go through a memory interface capable of dispatching mapped peripheral operations; a partial 16-bit unsigned multiplier is mapped, but real memory-map enforcement is not yet implemented. Multiplier results are immediate; signed, byte, accumulation, fractional and 32-bit modes are not implemented.

The instructor's basic blink program has been tested end-to-end. Classic double-operand ADDC, SUBC, DADD, BIT and BIC are also supported, alongside the earlier subset; RRC, RRA, SWPB, SXT and PUSH support R4–R15 register, indexed, and indirect forms; CALL supports immediate and R4–R15 register forms. Other single-operand forms remain unsupported. DADD preserves the overflow flag, which the hardware specification leaves undefined. This is not a complete MSP430X CPU: only a subset of classic instructions and addressing modes has been implemented and it has not been validated comprehensively. Unsupported instructions stop execution, but some unsupported hardware register writes may be silently stored without hardware effects. Do not assume that every valid program works. Watchdog, clocks, port multiplexing, timers, interrupts, serial, ADC, USB, low-power modes and most peripherals are not simulated. Button inputs and P1/P2/P4 GPIO are approximations, updated in batches by the CPU worker; P2.1 and P1.1 are assumed high when released. A floating input is assumed low unless an internal resistor or external override is selected. Pin contention and electrical effects are not modeled.

CPU execution runs independently of GUI frames and is paced using experimental classic-instruction cycle counts and an adjustable assumed MCLK (default 1,048,576 Hz, a nominal settled configuration). Clock control registers and oscillator startup are not simulated. TI SLAU208Q sections 5.2 and 6.5.1.5 are the references. The emulator warns if it falls more than 100 ms behind, and actual speed can vary with system load. The tested blink instruction sequence has cycle-count tests; other combinations and wall-clock timing are not comprehensively validated. Do not rely on this simulator for timing, frequency, phase, duty-cycle, power or hardware correctness. The illustrated board is schematic, and header graphics are decorative. The GPIO selector can set input levels.

`simulator.py` remains the legacy Tkinter host-C simulator; unlike the new firmware mode, it compiles and runs native Windows code **without a sandbox**. Only run trusted code there. MSP430 firmware execution is experimental and is not a security boundary either; do not run untrusted source.

References: `../msp430f5529.pdf` (TI SLAS590P) and the device support headers and linker files distributed with TI MSP430 GCC. The separate `../MSP430-Emulator` targets a different MCU and was not incorporated into this CPU implementation.

### Emulator speed

Firmware mode batches common MSP430 instructions in a native host interpreter. On first use it builds a local library from `cpu_batch.c` with host `gcc` (e.g. MinGW-w64 on Windows, matching Python's architecture) and caches it in `__pycache__`. This is separate from TI's cross-compiler. The status shows `native batches` when active or `Python fallback` if the native build or load fails. Single stepping, mapped-device accesses and unaccelerated instructions retain the Python reference behavior. This improves throughput, not hardware timing fidelity. Run `python benchmark_cpu.py` from the project root to compare unpaced execution and measure actual blink intervals using the firmware worker.

### S1 button exercise

In the GUI, open `button_toggle.c` and click **Run**. Press **S1 (P2.1)** on the board drawing: the red **P1.0** LED toggles and stays that way when released. Press again to turn it off. S2 (P1.1) is independent. The switches are momentary, active-low inputs; the example polls the pin with a pull-up and debounces both edges. It does not require GPIO interrupts.
