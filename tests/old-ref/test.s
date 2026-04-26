.text
.global main

main:
    LDI   r1, 10
    LDI   r2, 3

    ADD   r3, r1, r2
    SUB   r4, r1, r2
    AND   r5, r1, r2
    OR    r6, r1, r2
    SLT   r7, r2, r1

    ADDI  r1, r1, 1
    SLL   r2, r2, 1
    SRL   r2, r2, 1

    ST    r3, result(r0)
    LD    r4, result(r0)

    BEZ   r4, after_skip
    BNZ   r4, do_call

after_skip:
    LDI   r5, 99

do_call:
    JL    r7, func
    HALT

    NOP

func:
    LDI   r1, 42
    JR    r7

    ADDI  r1, r1, 1

.data
result: .word 0
