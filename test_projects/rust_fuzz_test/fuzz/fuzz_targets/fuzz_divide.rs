#![no_main]

use libfuzzer_sys::fuzz_target;
use rust_fuzz_test::divide_numbers;

fuzz_target!(|data: &[u8]| {
    // Fuzz the divide_numbers function which has division by zero
    let _ = divide_numbers(data);
});
