module pc (
    input wire clk,
    input wire reset,
    input wire [15:0] pc_next,  // what to load next
    output reg [15:0] pc  // current PC
);
    always @(posedge clk or posedge reset) begin
        if (reset)
            pc <= 16'h0000;
        else
            pc <= pc_next;
    end
endmodule
