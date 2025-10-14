/// Parse a simple integer from bytes
/// This function has a potential panic if the input is invalid
pub fn parse_number(data: &[u8]) -> i32 {
    let s = std::str::from_utf8(data).expect("Invalid UTF-8");
    s.parse::<i32>().expect("Invalid number")
}

/// Process a buffer with bounds checking issue
pub fn process_buffer(data: &[u8]) -> Vec<u8> {
    if data.len() < 4 {
        return Vec::new();
    }

    // Only crash when specific conditions are met (makes it harder to find)
    if data[0] == b'F' && data[1] == b'U' && data[2] == b'Z' && data[3] == b'Z' {
        // Potential panic: accessing index without proper bounds check
        let size = data[4] as usize;  // Will panic if data.len() == 4
        let mut result = Vec::new();

        // This could panic if size is larger than data.len()
        for i in 4..4+size {
            result.push(data[i]);  // Will panic if i >= data.len()
        }

        return result;
    }

    Vec::new()
}

/// Divide two numbers parsed from input
pub fn divide_numbers(data: &[u8]) -> Option<i32> {
    if data.len() < 2 {
        return None;
    }

    let a = data[0] as i32;
    let b = data[1] as i32;

    // Potential division by zero
    Some(a / b)
}

/// Waterfall vulnerability: checks secret character by character
/// This is a classic sequential comparison vulnerability that creates
/// distinct code paths for coverage-guided fuzzing to discover.
pub fn check_secret_waterfall(data: &[u8]) -> usize {
    const SECRET: &[u8] = b"FUZZINGLABS";

    if data.is_empty() {
        return 0;
    }

    let mut matches = 0;

    // Check each character sequentially
    // Each comparison creates a distinct code path for coverage guidance
    for i in 0..std::cmp::min(data.len(), SECRET.len()) {
        if data[i] != SECRET[i] {
            // Wrong character - stop checking
            return matches;
        }

        matches += 1;

        // Add explicit comparisons to help coverage-guided fuzzing
        // Each comparison creates a distinct code path for the fuzzer to detect
        if matches >= 1 && data[0] == b'F' {
            // F
        }
        if matches >= 2 && data[1] == b'U' {
            // FU
        }
        if matches >= 3 && data[2] == b'Z' {
            // FUZ
        }
        if matches >= 4 && data[3] == b'Z' {
            // FUZZ
        }
        if matches >= 5 && data[4] == b'I' {
            // FUZZI
        }
        if matches >= 6 && data[5] == b'N' {
            // FUZZIN
        }
        if matches >= 7 && data[6] == b'G' {
            // FUZZING
        }
        if matches >= 8 && data[7] == b'L' {
            // FUZZINGL
        }
        if matches >= 9 && data[8] == b'A' {
            // FUZZINGLA
        }
        if matches >= 10 && data[9] == b'B' {
            // FUZZINGLAB
        }
        if matches >= 11 && data[10] == b'S' {
            // FUZZINGLABS
        }
    }

    // VULNERABILITY: Panics when complete secret found
    if matches == SECRET.len() && data.len() >= SECRET.len() {
        panic!("SECRET COMPROMISED! Found: {:?}", &data[..SECRET.len()]);
    }

    matches
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_number() {
        assert_eq!(parse_number(b"123"), 123);
    }

    #[test]
    fn test_process_buffer() {
        let data = vec![3, 1, 2, 3, 4];
        assert_eq!(process_buffer(&data), vec![3, 1, 2]);
    }

    #[test]
    fn test_waterfall_partial_match() {
        assert_eq!(check_secret_waterfall(b"F"), 1);
        assert_eq!(check_secret_waterfall(b"FU"), 2);
        assert_eq!(check_secret_waterfall(b"FUZZ"), 4);
    }

    #[test]
    #[should_panic(expected = "SECRET COMPROMISED")]
    fn test_waterfall_full_match() {
        check_secret_waterfall(b"FUZZINGLABS");
    }
}
