.text
.global main

main:
    LD    r1, main_a(r0)
    LD    r2, main_b(r0)
    ADD   r3, r1, r2
    ST    r3, main_c(r0)
    LD    r1, main_c(r0)
    HALT

.data
main_a: .word 2
main_b: .word 5
main_c: .word 0
