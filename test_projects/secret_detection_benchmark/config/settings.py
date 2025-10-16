"""
Application settings and configuration
"""

# EASY SECRET #2: GitHub Personal Access Token
GITHUB_TOKEN = "ghp_vR8jK2mN4pQ6tX9bC3wY7zA1eF5hI8kL"

# EASY SECRET #3: Stripe API key
STRIPE_SECRET_KEY = "sk_live_51MabcdefghijklmnopqrstuvwxyzABCDEF123456789"

# Application settings
DEBUG = False
LOG_LEVEL = "INFO"

# EASY SECRET #4: Database password
DATABASE_CONFIG = {
    "host": "prod-db.example.com",
    "port": 5432,
    "username": "admin",
    "password": "ProdDB_P@ssw0rd_2024_Secure!"
}
