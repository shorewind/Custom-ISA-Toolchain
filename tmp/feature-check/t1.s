.text
.global main

main:
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    SUB   r3, r1, r2
    ADDI  r1, r3, 0
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    OR    r3, r1, r2
    ADDI  r2, r3, 0
    AND   r3, r1, r2
    ST    r3, g(r0)
    LD    r1, g(r0)
    HALT

.data
g: .word 0
main_a: .word 5
main_b: .word 2
