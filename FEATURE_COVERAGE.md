# MSP430F5529 feature coverage and acceptance baseline

This is a proposed fixed set of firmware scenarios, not a claim of current 80% coverage. A scenario passes only after its behavior is implemented and tested against documented device behavior. Current automated tests do not yet prove hardware equivalence.

| Scenario | Status |
| --- | --- |
| Compiled GPIO LED blink | Partial: tested with approximate GPIO and timing |
| GPIO input and pull resistor | Partial: batched teaching approximation |
| GPIO edge interrupt | Unsupported |
| CPU classic instructions and addressing | Partial |
| CPUX 20-bit addressing and extended instructions | Unsupported |
| Interrupt entry, priority, and return | Unsupported |
| Watchdog reset and interval interrupt | Unsupported |
| Clock selection and dividers | Unsupported |
| Low-power entry and interrupt wakeup | Unsupported |
| Timer_A periodic interrupt | Unsupported |
| Timer_A PWM output | Unsupported |
| Timer_B compare and capture | Unsupported |
| UART transmission and reception | Unsupported |
| SPI data exchange | Unsupported |
| I2C data exchange | Unsupported |
| ADC12 input conversion and interrupt | Unsupported |
| Hardware multiplier | Partial: immediate 16-bit unsigned word multiplication only; no hardware latency |
| CRC module | Unsupported |
| DMA transfer | Unsupported |
| RTC interrupt | Unsupported |
| USB enumeration and endpoint transfer | Unsupported |

The initial target is at least 17 of these 21 scenarios passing (80%, rounded up). Each must have an automated firmware-level acceptance test; narrowly tested approximations do not count as passing. USB is included, not silently excluded. Electrical accuracy, power consumption, analog noise, oscillator startup physics and hardware debugging are not claimed by this target.

The new memory interface allows peripheral register handlers to intercept CPU byte and word operations. Only the partial multiplier is mapped; unmapped locations remain RAM-like and GPIO remains batched; flash protection, register reset values and the real device memory map are not yet implemented. The raw `cpu.mem` compatibility view bypasses handlers and must not be used by future CPU or peripheral logic.
