#include <msp430.h>

/* Approx. 2 Hz at the simulator's default MCLK of 1,048,576 Hz. */
int main(void)
{
    WDTCTL = WDTPW | WDTHOLD;
    P1OUT |= BIT0;
    P4OUT &= ~BIT7;
    P1DIR |= BIT0;
    P4DIR |= BIT7;

    /* At the simulator's -O0 setting this countdown costs 11 cycles per
       iteration. Recalibrate if the clock, compiler, or optimization changes. */
    volatile unsigned int i;
    for (;;) {
        for (i = 23830; i > 0; --i) { }
        P1OUT ^= BIT0;
        P4OUT ^= BIT7;
    }
}
