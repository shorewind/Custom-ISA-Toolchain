module unified_mem (
    input clk,
    // instruction fetch (read-only)
    input wire [15:0] i_addr,
    output wire [15:0] i_data,
    // data access (load/store)
    input wire [15:0] d_addr,
    input wire [15:0] d_wdata,
    input wire d_read,
    input wire d_write,
    output wire [15:0] d_rdata
);

    reg [15:0] mem [0:1024-1];  // 1KiB memory space

    // instruction fetch
    assign i_data = mem[i_addr];
    // data read
    assign d_rdata = d_read ? mem[d_addr[8:0]] : 16'h0000;

    always @(posedge clk) begin
    // data write
        if (d_write)
            mem[d_addr] = d_wdata;
    end
    
endmodule
