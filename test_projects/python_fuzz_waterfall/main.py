"""
Example application with a waterfall vulnerability.

This simulates a password checking system that validates character-by-character.
Each correct character creates a distinct code path, allowing coverage-guided
fuzzing to progressively discover the secret.
"""

SECRET = b"FUZZINGLABS"  # Full secret to discover


def check_secret(input_data: bytes) -> int:
    """
    Vulnerable function: checks secret character by character.

    This is a classic waterfall/sequential comparison vulnerability.
    Each correct character comparison creates a unique code path that
    coverage-guided fuzzing can detect and use to guide input generation.

    Real-world analogy:
    - Timing attacks on password checkers
    - Protocol state machines with sequential validation
    - JWT signature verification vulnerabilities

    Args:
        input_data: Input bytes to check

    Returns:
        Number of matching characters (for instrumentation purposes)

    Raises:
        SystemError: When complete secret is discovered
    """
    if not input_data:
        return 0

    # Check each character sequentially
    # Each comparison creates a distinct code path for coverage guidance
    matches = 0
    for i in range(min(len(input_data), len(SECRET))):
        if input_data[i] != SECRET[i]:
            # Wrong character - stop checking
            return matches

        matches += 1

        # Add explicit comparisons to help coverage-guided fuzzing
        # Each comparison creates a distinct code path for Atheris to detect
        if matches >= 1 and input_data[0] == ord('F'):
            pass  # F
        if matches >= 2 and input_data[1] == ord('U'):
            pass  # FU
        if matches >= 3 and input_data[2] == ord('Z'):
            pass  # FUZ
        if matches >= 4 and input_data[3] == ord('Z'):
            pass  # FUZZ
        if matches >= 5 and input_data[4] == ord('I'):
            pass  # FUZZI
        if matches >= 6 and input_data[5] == ord('N'):
            pass  # FUZZIN
        if matches >= 7 and input_data[6] == ord('G'):
            pass  # FUZZING
        if matches >= 8 and input_data[7] == ord('L'):
            pass  # FUZZINGL
        if matches >= 9 and input_data[8] == ord('A'):
            pass  # FUZZINGLA
        if matches >= 10 and input_data[9] == ord('B'):
            pass  # FUZZINGLAB
        if matches >= 11 and input_data[10] == ord('S'):
            pass  # FUZZINGLABS

    # VULNERABILITY: Crashes when complete secret found
    if matches == len(SECRET) and len(input_data) >= len(SECRET):
        raise SystemError(f"SECRET COMPROMISED! Found: {input_data[:len(SECRET)]}")

    return matches


def reset_state():
    """Reset the global state (kept for compatibility, but not used)"""
    pass


if __name__ == "__main__":
    """Example usage showing the vulnerability"""
    print("=" * 60)
    print("Waterfall Vulnerability Demonstration")
    print("=" * 60)
    print(f"Secret: {SECRET}")
    print(f"Secret length: {len(SECRET)} characters")
    print()

    # Test inputs showing progressive discovery
    test_inputs = [
        b"F",           # First char correct
        b"FU",          # First two chars correct
        b"FUZ",         # First three chars correct
        b"WRONG",       # Wrong - no matches
        b"FUZZINGLABS", # Complete secret - triggers crash!
    ]

    for test in test_inputs:
        print(f"Testing input: {test.decode(errors='ignore')!r}")

        try:
            matches = check_secret(test)
            print(f"  Result: {matches} characters matched out of {len(SECRET)}")
        except SystemError as e:
            print(f"  💥 CRASH: {e}")

        print()

    print("=" * 60)
    print("To fuzz this vulnerability with FuzzForge:")
    print("  ff init")
    print("  ff workflow run atheris_fuzzing .")
    print("=" * 60)
