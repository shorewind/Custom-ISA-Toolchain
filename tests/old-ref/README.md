# Old Reference Artifacts

This directory holds legacy hand-written or historical reference files that are
useful for manual comparison against the current compiler and assembler, but
are not part of the main fixture layout under `tests/basic/`,
`tests/feature-check/`, or `tests/ir-regression/`.

Contents include:

- `c-instr-ref.c`: older instruction-oriented compiler reference source.
- `assembly-instr-ref.s`: older instruction-oriented hand-written assembly.
- `assembly-control-ref.s`: older control-flow-oriented hand-written assembly.
- `test.s`: extra legacy assembly scratch/reference file kept for manual comparison.
- `imem-instr-ref.memh` / `imem-instr-ref.memb`: historical assembled image for
  the instruction reference.
- `imem-control-ref.memh`: historical assembled image for the control-flow
  reference.

These files reflect older layout assumptions such as fixed `.data` placement or
shorter memory images, so exact byte-for-byte matches are not always expected
under the current toolchain defaults. They are best used for semantic and
encoding cross-checks rather than snapshot equivalence.
