# ISA Directory

This directory contains hardware-simulation artifacts referenced by the
toolchain report.

Contents:

- `output.txt`: captured Questa execution trace and final register/memory dump
  for the arithmetic example.
- `simulate.txt`: captured Questa compile/load output for the same run.
- `simulation/`: Verilog simulation sources used for processor-level
  validation, including `tb_cpu.v` and supporting HDL modules.
- `Custom ISA Technical Report.pdf`: a PDF copy of the separate ISA report.

The processor hardware design itself is maintained separately from this
toolchain repository. For the standalone custom ISA hardware repository, see:

- `https://github.com/shorewind/Custom-ISA`

Within this toolchain repository, the `simulation/` subtree is included so the
report can reference the exact testbench and supporting HDL used for the
Questa arithmetic example.
