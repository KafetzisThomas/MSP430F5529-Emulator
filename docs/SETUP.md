# Windows setup and troubleshooting

This project has been exercised on Windows with Python 3.14.2 and `imgui-bundle` 1.93.0. Other platforms and Python versions have not been established. You need Python with Tkinter, pip, and a graphical desktop. Run the commands below in **Command Prompt** from the repository root.

## Install the Python dependency

```cmd
python -m pip install -r requirements.txt
```

## Configure the MSP430 compiler

Obtain TI's Windows MSP430 GCC toolchain and MSP430 GCC support files separately; neither is included in a fresh checkout. The application looks for:

```text
%LOCALAPPDATA%\MSP430SimToolchain\bin\msp430-elf-gcc.exe
%LOCALAPPDATA%\MSP430SimSupport\include\msp430f5529.h
```

The support `include` directory must also contain the appropriate device linker files. The original setup uses `msp430-gcc-9.3.1.11_win64` and `msp430-gcc-support-files` directories with directory junctions, because the compiler driver can fail when its installation path contains spaces.

If those directories are at the repository root and the destination paths above **do not already exist**, create the junctions:

```cmd
mklink /J "%LOCALAPPDATA%\MSP430SimToolchain" "%CD%\msp430-gcc-9.3.1.11_win64"
mklink /J "%LOCALAPPDATA%\MSP430SimSupport" "%CD%\msp430-gcc-support-files"
```

Adjust the targets for your extracted directories. Do not overwrite existing destinations; inspect them first. If a target moves or you change Windows accounts, update the setup accordingly.

## Launch and check

```cmd
python simulator_imgui.py
```

Alternatively, double-click `run.bat`. The editor opens with a built-in blink example. Click **Run firmware**. If compilation and execution succeed, the status changes to running and the illustrated P1.0 LED should blink. Inspect **Build output** if there is an error.

A separate host `gcc` on PATH, matching Python's architecture, is optional for native instruction batching. If it cannot be built or loaded, the firmware runner uses the Python fallback; the status identifies the active mode. This host compiler is distinct from TI's cross-compiler.

## Troubleshooting

- **Compiler cannot start:** check the exact `%LOCALAPPDATA%` paths, junction targets, and Windows compiler executable.
- **Build fails:** inspect **Build output**; verify device headers, linker files, and your C source.
- **CPU stops:** the firmware may use an unsupported instruction or peripheral operation; inspect the log and [feature coverage](../FEATURE_COVERAGE.md).
- **Slow execution / Python fallback:** check host `gcc` and architecture. Native batching does not guarantee real-time operation.
- **GUI fails to start:** check that Tkinter and `imgui-bundle` are installed for the selected Python interpreter and that a graphical session is available.

See [contributing](../CONTRIBUTING.md) for the full test suite and its additional prerequisites.
