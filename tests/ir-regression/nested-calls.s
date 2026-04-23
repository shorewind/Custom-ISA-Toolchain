.text
.global main

inc:
    LD    r1, inc_p_val_x(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, inc_t0(r0)
    LD    r1, inc_t0(r0)
    JR    r7

add:
    LD    r1, add_p_val_x(r0)
    LD    r2, add_p_val_y(r0)
    ADD   r3, r1, r2
    ST    r3, add_t0(r0)
    LD    r1, add_t0(r0)
    JR    r7

main:
    LD    r3, main_a(r0)
    ST    r3, inc_p_val_x(r0)
    JL    r7, inc
    ST    r1, main_t0(r0)
    LDI   r3, 4
    ST    r3, inc_p_val_x(r0)
    JL    r7, inc
    ST    r1, main_t1(r0)
    LD    r3, main_t0(r0)
    ST    r3, add_p_val_x(r0)
    LD    r3, main_t1(r0)
    ST    r3, add_p_val_y(r0)
    JL    r7, add
    ST    r1, main_t2(r0)
    LD    r1, main_t2(r0)
    HALT

.data
inc_p_val_x: .word 0
inc_t0: .word 0
add_p_val_x: .word 0
add_p_val_y: .word 0
add_t0: .word 0
main_a: .word 3
main_t0: .word 0
main_t1: .word 0
main_t2: .word 0
