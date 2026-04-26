.text
.global main

main:
while_start_1:
    LD    r1, main_i(r0)
    LDI   r2, 2
    SLT   r3, r1, r2
    BEZ   r3, while_end_1
    LD    r1, main_s(r0)
    LD    r2, main_i(r0)
    ADD   r3, r1, r2
    ST    r3, main_s(r0)
    LD    r1, main_i(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, main_i(r0)
    BEZ   r0, while_start_1
while_end_1:
    LD    r3, main_s(r0)
    ST    r3, g(r0)
    LD    r1, g(r0)
    HALT

.data
g: .word 0
main_i: .word 0
main_s: .word 0
