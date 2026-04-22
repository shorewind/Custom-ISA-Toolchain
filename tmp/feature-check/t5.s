.text
.global main

inc:
    LD    r1, inc_p_val_x(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, inc_p_val_x(r0)
    LD    r1, inc_p_val_x(r0)
    JR    r7

main:
    LD    r3, main_a(r0)
    ST    r3, inc_p_val_x(r0)
    JL    r7, inc
    ADDI  r3, r1, 0
    ST    r3, g(r0)
    LD    r1, main_a(r0)
    HALT

.data
g: .word 0
inc_p_val_x: .word 0
main_a: .word 4
