module sign_extend #(parameter IN_WIDTH = 7) (
    input [IN_WIDTH-1:0] data_in,
    output wire [15:0] data_extended
);

    // sign extend to 16 bits
    wire sign = data_in[IN_WIDTH-1];
    assign data_extended = {{(16-IN_WIDTH){sign}}, data_in};
    
endmodule
