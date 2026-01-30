#![no_main]

use libfuzzer_sys::fuzz_target;
use rust_fuzz_test::process_buffer;

fuzz_target!(|data: &[u8]| {
    // Fuzz the process_buffer function which has bounds checking issues
    let _ = process_buffer(data);
});
