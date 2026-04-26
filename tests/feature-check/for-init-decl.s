.text
.global main

main:
for_start_1:
    LD    r1, main_i(r0)
    LDI   r2, 3
    SLT   r3, r1, r2
    BEZ   r3, for_end_1
    LD    r1, main_s(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, main_s(r0)
    LD    r1, main_i(r0)
    LDI   r2, 1
    ADD   r3, r1, r2
    ST    r3, main_i(r0)
    BEZ   r0, for_start_1
for_end_1:
    LD    r1, main_s(r0)
    HALT

.data
main_s: .word 0
main_i: .word 0
