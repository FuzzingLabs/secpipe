"""
Application settings with sensitive configuration
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


# Database configuration with passwords
DATABASE_CONFIG = {
    'host': 'db.production.internal',
    'port': 5432,
    'username': 'postgres',
    'password': 'postgres_password_123',  # Hardcoded password
    'database': 'production_db'
}

# API Keys and tokens
GITHUB_TOKEN = "ghp_1234567890abcdef1234567890abcdef123456"
GITLAB_TOKEN = "glpat-1234567890abcdefghij"
SLACK_WEBHOOK = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
SENDGRID_API_KEY = "SG.1234567890.abcdefghijklmnopqrstuvwxyz"

# OAuth credentials
OAUTH_CLIENT_ID = "1234567890-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "GOCSPX-1234567890abcdefghijklmn"

# Encryption keys
ENCRYPTION_KEY = "ThisIsAVerySecretEncryptionKey123!"
JWT_SECRET = "super_secret_jwt_key_do_not_share"

# Cloud provider credentials
AZURE_STORAGE_KEY = "DefaultEndpointsProtocol=https;AccountName=storage;AccountKey=1234567890abcdefghijklmnopqrstuvwxyz==;EndpointSuffix=core.windows.net"
GCP_SERVICE_ACCOUNT = {
    "type": "service_account",
    "project_id": "my-project",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkq...fake...key\n-----END PRIVATE KEY-----",
    "client_email": "service@project.iam.gserviceaccount.com"
}

# Payment provider keys
PAYPAL_CLIENT_ID = "AZDxjDScFpQtjWTOUtWKbyN_bDt4OgqaF4eYXlewfBP4-8aqX3PiV8e1GWU6liB2CUXlkA59kJXE7M6R"
PAYPAL_CLIENT_SECRET = "EGnHDxD_qRPdaLdZz8iCr8N7_MzF-YHPTkjs6NKYQvQSBngp4PTTVWkPZRbL"

# Dangerous configuration
DEBUG = True  # Debug mode enabled in production
ALLOW_ALL_ORIGINS = "*"  # CORS vulnerability
USE_SSL = False  # SSL disabled