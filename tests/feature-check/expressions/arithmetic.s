.text
.global main

main:
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    SUB   r3, r1, r2
    ST    r3, main_t0(r0)
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    OR    r3, r1, r2
    ST    r3, main_t1(r0)
    LD    r1, main_t0(r0)
    LD    r2, main_t1(r0)
    AND   r3, r1, r2
    ST    r3, g(r0)
    LD    r1, g(r0)
    HALT

.data
g: .word 0
main_a: .word 5
main_b: .word 2
main_t0: .word 0
main_t1: .word 0
