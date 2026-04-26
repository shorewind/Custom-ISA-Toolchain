.text
.global main

main:
    LDI   r1, 2
    LDI   r2, 3
if:
    SLT   r4, r1, r2
    BEZ   r4, else
    LDI   r3, 1
    BNZ   r4, after_if
else:
    LDI   r3, 2
after_if:
    LDI   r5, 0

loop_top:
    SLT   r6, r5, r1
    BEZ   r6, loop_end
    ADDI  r5, r5, 1
    BNZ   r6, loop_top

loop_end:
    LDI   r6, 0
    LDI   r4, 0

for_top:
    SLT   r7, r6, r2
    BEZ   r7, for_end
    ADD   r4, r4, r6
    ADDI  r6, r6, 1
    BNZ   r7, for_top

for_end:
    LDI   r1, 10
    JL    r7, inc
    ADDI  r1, r1, 0
    HALT

inc:
    ADDI  r1, r1, 1
    JR    r7
