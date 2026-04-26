.text
.global main

main:
    LDI   r3, 1
    ST    r3, a(r0)
    LDI   r3, 2
    ST    r3, a+1(r0)
    LD    r3, a(r0)
    ST    r3, main_t0(r0)
    LD    r3, a+1(r0)
    ST    r3, main_t1(r0)
    LD    r1, main_t0(r0)
    LD    r2, main_t1(r0)
    ADD   r3, r1, r2
    ST    r3, g(r0)
    LD    r1, g(r0)
    HALT

.data
g: .word 0
a: .word 0
a_1: .word 0
main_t0: .word 0
main_t1: .word 0
