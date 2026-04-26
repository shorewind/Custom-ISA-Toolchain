.text
.global main

main:
    LD    r1, main_a(r0)
    LDI   r2, 3
    SUB   r3, r1, r2
    BNZ   r3, if_else_1
    LD    r1, main_r(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, main_r(r0)
    BEZ   r0, if_end_1
if_else_1:
if_end_1:
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    SUB   r3, r1, r2
    BEZ   r3, if_else_2
    LD    r1, main_r(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, main_r(r0)
    BEZ   r0, if_end_2
if_else_2:
if_end_2:
    LD    r1, main_b(r0)
    LD    r2, main_a(r0)
    SLT   r3, r2, r1
    BEZ   r3, if_else_3
    LD    r1, main_r(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, main_r(r0)
    BEZ   r0, if_end_3
if_else_3:
if_end_3:
    LD    r3, main_r(r0)
    ST    r3, g(r0)
    LD    r1, g(r0)
    HALT

.data
g: .word 0
main_a: .word 3
main_b: .word 5
main_r: .word 0
