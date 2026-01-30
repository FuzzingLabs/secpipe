"""
Database connection module with various security issues
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

import mysql.connector
import pickle
import os

# Hardcoded database credentials (will trigger secret detection)
DB_HOST = "production.database.com"
DB_USER = "admin"
DB_PASSWORD = "SuperSecretPassword123!"
API_KEY = "sk-1234567890abcdef1234567890abcdef"
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

class DatabaseManager:
    def __init__(self):
        self.connection = None

    def connect(self):
        """Connect to database with hardcoded credentials"""
        self.connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database="production"
        )

    def execute_query(self, user_input):
        """Vulnerable to SQL injection - concatenating user input"""
        query = "SELECT * FROM users WHERE username = '" + user_input + "'"
        cursor = self.connection.cursor()
        cursor.execute(query)  # SQL injection vulnerability
        return cursor.fetchall()

    def search_products(self, search_term, category):
        """Another SQL injection vulnerability using string formatting"""
        query = f"SELECT * FROM products WHERE name LIKE '%{search_term}%' AND category = '{category}'"
        cursor = self.connection.cursor()
        cursor.execute(query)
        return cursor.fetchall()

    def update_user_profile(self, user_id, data):
        """SQL injection via string interpolation"""
        query = "UPDATE users SET profile = '%s' WHERE id = %s" % (data, user_id)
        cursor = self.connection.cursor()
        cursor.execute(query)
        self.connection.commit()

    def load_user_preferences(self, data):
        """Insecure deserialization vulnerability"""
        user_prefs = pickle.loads(data)  # Dangerous pickle deserialization
        return user_prefs

    def backup_database(self, backup_name):
        """Command injection vulnerability"""
        os.system(f"mysqldump -u {DB_USER} -p{DB_PASSWORD} production > {backup_name}")

    def get_user_by_id(self, user_id):
        """Dynamic query building - potential SQL injection"""
        base_query = "SELECT * FROM users"
        where_clause = " WHERE id = " + str(user_id)
        final_query = base_query + where_clause
        cursor = self.connection.cursor()
        cursor.execute(final_query)
        return cursor.fetchone()