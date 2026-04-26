.text
.global main

main:
    LD    r1, main_a(r0)
    LDI   r2, 1
    SLT   r3, r1, r2
    BNZ   r3, if_else_1
    LDI   r3, 7
    ST    r3, g(r0)
    BEZ   r0, if_end_1
if_else_1:
    LDI   r3, 3
    ST    r3, g(r0)
if_end_1:
    LD    r1, g(r0)
    HALT

.data
g: .word 0
main_a: .word 1
