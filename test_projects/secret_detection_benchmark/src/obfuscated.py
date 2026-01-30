"""
Heavily obfuscated secrets - hard to detect
"""
import codecs

# HARD SECRET #21: ROT13 encoded secret
SECRET_ROT13 = "fx_yvir_frperg_xrl_12345"

# HARD SECRET #22: Binary string representation
GITHUB_TOKEN_BYTES = b'\x67\x68\x70\x5f\x4d\x79\x47\x69\x74\x48\x75\x62\x54\x6f\x6b\x65\x6e\x31\x32\x33\x34\x35\x36'

# HARD SECRET #23: Character array join
AWS_SECRET_CHARS = ['A','W','S','_','S','E','C','R','E','T','_','K','E','Y','_','X','Y','Z','7','8','9']
AWS_SECRET = ''.join(AWS_SECRET_CHARS)

# HARD SECRET #24: Reversed string that's un-reversed at runtime
TOKEN_REVERSED = "321cba_desrever_nekot_ipa"

def get_rot13_secret():
    return codecs.decode(SECRET_ROT13, 'rot_13')

def get_token():
    return TOKEN_REVERSED[::-1]
