#!/usr/bin/env python3
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

"""
Test vulnerable application for FuzzForge security scanning.
Contains intentional security vulnerabilities for testing purposes.
"""

import subprocess
import sqlite3

# Hardcoded secrets (for secret detection testing)
API_KEY = "sk-1234567890abcdef1234567890abcdef"
DATABASE_PASSWORD = "admin123"
JWT_SECRET = "my-super-secret-jwt-key-dont-tell-anyone"

def unsafe_sql_query(user_id):
    """SQL injection vulnerability"""
    conn = sqlite3.connect("test.db")
    cursor = conn.cursor()
    # Vulnerable: direct string interpolation
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchall()

def unsafe_command_execution(filename):
    """Command injection vulnerability"""
    # Vulnerable: unsanitized user input in shell command
    result = subprocess.run(f"ls -la {filename}", shell=True, capture_output=True)
    return result.stdout

def unsafe_file_access(filepath):
    """Path traversal vulnerability"""
    # Vulnerable: no path validation
    with open(f"/var/app/uploads/{filepath}", "r") as f:
        return f.read()

def main():
    """Main application function"""
    print("Vulnerable app started")
    print(f"Using API key: {API_KEY}")

if __name__ == "__main__":
    main()