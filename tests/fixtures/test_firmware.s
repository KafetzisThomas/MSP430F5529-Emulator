	.file	"test_firmware.c"
.text
	.balign 2
	.global	main
	.type	main, @function
main:
; start of function
; framesize_regs:     0
; framesize_locals:   2
; framesize_outgoing: 0
; framesize:          2
; elim ap -> fp       2
; elim fp -> sp       2
; saved regs:(none)
	; start of prologue
	SUB.W	#2, R1
	; end of prologue
	MOV.W	#23168, &WDTCTL
	MOV.B	&PADIR_L, R12
	BIS.B	#1, R12
	AND	#0xff, R12
	MOV.B	R12, &PADIR_L
.L4:
	MOV.B	&PAOUT_L, R12
	XOR.B	#1, R12
	AND	#0xff, R12
	MOV.B	R12, &PAOUT_L
	MOV.W	#10000, @R1
	BR	#.L2
.L3:
	MOV.W	@R1, R12
	ADD.W	#-1, R12
	MOV.W	R12, @R1
.L2:
	MOV.W	@R1, R12
	CMP.W	#0, R12 { JNE	.L3
	BR	#.L4
	.size	main, .-main
	.ident	"GCC: (Mitto Systems Limited - msp430-gcc 9.3.1.11) 9.3.1"
	.mspabi_attribute 4, 2
	.mspabi_attribute 6, 1
	.mspabi_attribute 8, 1
	.gnu_attribute 4, 1
