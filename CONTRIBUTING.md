# Contributing

## Local setup

Use the Windows setup in the [README](README.md#quick-start-windows), including the Python dependency, MSP430 cross-compiler and support files. A host `gcc` and graphical desktop are also needed for the complete test suite. Toolchains and local GUI settings are intentionally ignored by Git.

## Validate changes

From the project root in Command Prompt:

```cmd
python -m unittest discover -v
```

Tests cover the CPU subset, memory and multiplier, native batching, GUI model, firmware and legacy simulator. Some tests build and run native programs; the GUI smoke test opens a window. Native batch tests are skipped when the backend cannot load. A passing subset or a skipped test is not proof of hardware equivalence.

For a focused check without compilers or a GUI:

```cmd
python -m unittest -v tests.test_memory tests.test_multiplier
```

When changing CPU or peripheral behavior, add focused regression tests and describe the hardware reference and limitations. For GUI or timing changes, describe any manual checks and the environment. Avoid committing generated binaries, downloaded toolchains, local settings, or reference documents.

## Proposing changes

Keep changes focused and explain the problem, approach, tests run, and any remaining limitations in a pull request. Report failures and skipped or unrun checks rather than describing them as passes. Review the project's [noncommercial source-available license](LICENSE) and ensure you have the necessary rights to submit your contribution. Third-party material retains its own terms.
