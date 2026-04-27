module reg_file (
    input wire clk,
    input wire enable,  // RegWrite enable
    input wire [2:0]  rs, rt, rd,  // input registers
    input wire [15:0] wd,  // write data
    output wire [15:0] vrs, vrt   // values read from registers
);
  
    reg [15:0] r[0:7];  // 8 x 16-bit registers

    // read registers
    assign vrs = (rs == 3'd0) ? 16'h0000 : r[rs];
    assign vrt = (rt == 3'd0) ? 16'h0000 : r[rt];

    // write on clock rising edge, ignore writes to r0
    always @(posedge clk) begin
        if (enable && (rd != 3'd0))
            r[rd] <= wd;
        r[0] <= 16'h0000; // keep $zero = 0
    end
endmodule
