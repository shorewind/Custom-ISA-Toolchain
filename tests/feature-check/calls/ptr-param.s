.text
.global main

bump:
    LD    r5, bump_p_ptr_x(r0)
    LD    r3, 0(r5)
    ST    r3, bump_t0(r0)
    LD    r1, bump_t0(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, bump_t1(r0)
    LD    r3, bump_t1(r0)
    LD    r5, bump_p_ptr_x(r0)
    ST    r3, 0(r5)
    LD    r5, bump_p_ptr_x(r0)
    LD    r3, 0(r5)
    ST    r3, bump_t2(r0)
    LD    r1, bump_t2(r0)
    JR    r7

main:
    LD    r3, addr_main_a(r0)
    ST    r3, main_t0(r0)
    LD    r3, main_t0(r0)
    ST    r3, bump_p_ptr_x(r0)
    JL    r7, bump
    ST    r1, main_t1(r0)
    LD    r1, main_a(r0)
    HALT

.data
bump_p_ptr_x: .word 0
bump_t0: .word 0
bump_t1: .word 0
bump_t2: .word 0
main_a: .word 4
main_t0: .word 0
main_t1: .word 0
addr_main_a: .word main_a
