.text
.global main

func:
    LDI   r1, 42
    JR    r7

main:
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    ADD   r3, r1, r2
    ST    r3, main_c(r0)
    LD    r3, main_c(r0)
    ST    r3, result(r0)
    LD    r1, result(r0)
    LDI   r2, 0
    SUB   r3, r1, r2
    BEZ   r3, if_else_1
    JL    r7, func
    ST    r1, main_t0(r0)
    LD    r3, main_t0(r0)
    ST    r3, main_c(r0)
    BEZ   r0, if_end_1
if_else_1:
    LDI   r3, 99
    ST    r3, main_c(r0)
if_end_1:
    LD    r1, main_c(r0)
    HALT

.data
result: .word 0
main_a: .word 10
main_b: .word 3
main_c: .word 0
main_t0: .word 0
