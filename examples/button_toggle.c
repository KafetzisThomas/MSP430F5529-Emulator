#include <msp430.h>

/* S1 (P2.1) toggles the red LED (P1.0) once per momentary press. */
int main(void)
{
    WDTCTL = WDTPW | WDTHOLD;
    P1OUT &= ~BIT0;
    P1DIR |= BIT0;
    P2DIR &= ~BIT1;
    P2OUT |= BIT1;                 /* Select pull-up, not pull-down. */
    P2REN |= BIT1;

    for (;;) {
        while (P2IN & BIT1) { }       /* Wait for S1 to go low. */
        __delay_cycles(10000);        /* About 10 ms at 1 MHz. */
        if (P2IN & BIT1) continue;    /* Ignore a short pulse. */
        P1OUT ^= BIT0;

        do {
            while (!(P2IN & BIT1)) { } /* Holding S1 must not toggle again. */
            __delay_cycles(10000);
        } while (!(P2IN & BIT1));      /* Confirm release before rearming. */
    }
}
