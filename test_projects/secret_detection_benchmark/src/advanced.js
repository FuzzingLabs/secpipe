// Advanced obfuscation techniques

// HARD SECRET #25: Template string with escaping
const SECRET_TEMPLATE = `sk_${"prod"}_${"template"}_${"key"}_xyz`;

// HARD SECRET #26: Secret in regex pattern
const PASSWORD_REGEX = /password_regex_secret_789/;

// HARD SECRET #27: XORed secret (XOR with key 42)
const XOR_SECRET = [65,82,90,75,94,91,92,75,93,67,65,90,67,92,75,91,67,95];

function decodeXOR() {
    return String.fromCharCode(...XOR_SECRET.map(c => c ^ 42));
}

// HARD SECRET #28: Escaped JSON within string
const CONFIG_JSON = "{\"api_key\":\"sk_escaped_json_key_456\"}";

module.exports = { SECRET_TEMPLATE, decodeXOR };
