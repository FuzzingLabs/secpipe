"""
API handler with various security vulnerabilities
"""

# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

import os
import subprocess
import jwt

# More hardcoded secrets
SECRET_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z7VS5JJ...fake...private...key
-----END RSA PRIVATE KEY-----"""
STRIPE_API_KEY = "sk_live_4eC39HqLyjWDarjtT1zdp7dc"

class APIHandler:
    def __init__(self):
        self.token = SECRET_TOKEN

    def process_user_input(self, user_data):
        """Dangerous eval usage - code injection"""
        # This is extremely dangerous!
        result = eval(user_data)  # Code injection vulnerability
        return result

    def execute_command(self, command):
        """Command injection via subprocess with shell=True"""
        result = subprocess.call(command, shell=True)  # Command injection risk
        return result

    def run_system_command(self, filename):
        """Another command injection vulnerability"""
        os.system("cat " + filename)  # Command injection

    def process_template(self, template_string, data):
        """Template injection vulnerability"""
        compiled = compile(template_string, '<string>', 'exec')
        exec(compiled, data)  # Code execution vulnerability
        return data

    def generate_dynamic_function(self, code):
        """Dynamic function creation - code injection"""
        func = eval(f"lambda x: {code}")  # Dangerous eval
        return func

    def authenticate_user(self, token):
        """JWT token in code"""
        decoded = jwt.decode(token, SECRET_TOKEN, algorithms=["HS256"])
        return decoded

    def get_file_contents(self, filepath):
        """Path traversal vulnerability"""
        # No validation of filepath - could access any file
        with open(filepath, 'r') as f:
            return f.read()

    def log_user_action(self, user_input):
        """Log injection vulnerability"""
        log_message = f"User action: {user_input}"
        os.system(f"echo '{log_message}' >> /var/log/app.log")  # Command injection via logs