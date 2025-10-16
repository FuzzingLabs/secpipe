"""
Configuration with moderately obfuscated secrets
"""
import base64

# MEDIUM SECRET #11: Base64 encoded AWS key
AWS_KEY_ENCODED = "QUtJQUlPU0ZPRE5ON0VYQU1QTEU="

# MEDIUM SECRET #12: Hex-encoded API token
HEX_TOKEN = "6170695f746f6b656e5f616263313233787977373839"

# MEDIUM SECRET #13: Split secret concatenated at runtime
DB_PASS_PART1 = "MySecure"
DB_PASS_PART2 = "Password"
DB_PASS_PART3 = "2024!"
DATABASE_PASSWORD = DB_PASS_PART1 + DB_PASS_PART2 + DB_PASS_PART3

def get_aws_key():
    return base64.b64decode(AWS_KEY_ENCODED).decode()
