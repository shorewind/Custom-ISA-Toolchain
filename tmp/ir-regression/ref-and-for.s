.text
.global main

bump:
    LD    r6, bump_p_ref_x(r0)
    LD    r1, 0(r6)
    LDI   r2, 1
    ADD   r3, r1, r2
    LD    r6, bump_p_ref_x(r0)
    ST    r3, 0(r6)
    LD    r6, bump_p_ref_x(r0)
    LD    r1, 0(r6)
    JR    r7

main:
for_start_1:
    LD    r1, main_i(r0)
    LDI   r2, 3
    SLT   r3, r1, r2
    BEZ   r3, for_end_1
    LD    r3, addr_main_s(r0)
    ST    r3, main_t0(r0)
    LD    r3, main_t0(r0)
    ST    r3, bump_p_ref_x(r0)
    JL    r7, bump
    ST    r1, main_t1(r0)
    LD    r1, main_i(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, main_i(r0)
    BEZ   r0, for_start_1
for_end_1:
    LD    r1, main_s(r0)
    HALT

.data
bump_p_ref_x: .word 0
main_s: .word 0
main_i: .word 0
main_t0: .word 0
main_t1: .word 0
addr_main_s: .word main_s
