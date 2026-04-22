.text
.global main

main:
    LD    r1, main_i(r0)
    LD    r2, main_j(r0)
    ADD   r3, r1, r2
    ST    r3, main_t0(r0)
    LD    r5, addr_a(r0)
    LD    r2, main_t0(r0)
    ADD   r4, r5, r2
    LDI   r3, 7
    ST    r3, 0(r4)
    LD    r3, a+3(r0)
    ST    r3, main_t1(r0)
    LD    r1, main_t1(r0)
    HALT

.data
a: .word 0
a_1: .word 0
a_2: .word 0
a_3: .word 0
a_4: .word 0
a_5: .word 0
a_6: .word 0
a_7: .word 0
main_i: .word 1
main_j: .word 2
main_t0: .word 0
main_t1: .word 0
addr_a: .word a
