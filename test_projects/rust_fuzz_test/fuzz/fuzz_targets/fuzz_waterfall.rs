#![no_main]

use libfuzzer_sys::fuzz_target;
use rust_fuzz_test::check_secret_waterfall;

fuzz_target!(|data: &[u8]| {
    // Fuzz the waterfall vulnerability - sequential secret checking
    let _ = check_secret_waterfall(data);
});
