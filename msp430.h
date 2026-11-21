#ifndef SIMULATED_MSP430_H
#define SIMULATED_MSP430_H

/* Windows host approximation, not the TI device header or an MSP430 emulator. */
#include <stdint.h>
#include <stdlib.h>
#include <windows.h>

typedef struct {
    volatile uint8_t p1dir, p1out, p1in, p1ren;
    volatile uint8_t p2dir, p2out, p2in, p2ren;
    volatile uint8_t p4dir, p4out, p4in, p4ren;
    volatile uint16_t wdtctl;
} sim_registers;

static sim_registers *sim_regs;
static HANDLE sim_mapping;

static void sim_initialize(void) __attribute__((constructor));
static void sim_initialize(void) {
    const char *name = getenv("MSP430_SIM_MAPPING");
    if (!name) ExitProcess(100);
    sim_mapping = OpenFileMappingA(FILE_MAP_ALL_ACCESS, FALSE, name);
    if (!sim_mapping) ExitProcess(101);
    sim_regs = (sim_registers *)MapViewOfFile(sim_mapping, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(sim_registers));
    if (!sim_regs) ExitProcess(102);
}

#define P1DIR (sim_regs->p1dir)
#define P1OUT (sim_regs->p1out)
#define P1IN  (sim_regs->p1in)
#define P1REN (sim_regs->p1ren)
#define P2DIR (sim_regs->p2dir)
#define P2OUT (sim_regs->p2out)
#define P2IN  (sim_regs->p2in)
#define P2REN (sim_regs->p2ren)
#define P4DIR (sim_regs->p4dir)
#define P4OUT (sim_regs->p4out)
#define P4IN  (sim_regs->p4in)
#define P4REN (sim_regs->p4ren)
#define WDTCTL (sim_regs->wdtctl)
#define WDTPW 0x5A00u
#define WDTHOLD 0x0080u
#define BIT0 0x01u
#define BIT1 0x02u
#define BIT2 0x04u
#define BIT3 0x08u
#define BIT4 0x10u
#define BIT5 0x20u
#define BIT6 0x40u
#define BIT7 0x80u

#endif
