"""
Main application entry point
"""
import os

# EASY SECRET #5: JWT Secret
JWT_SECRET_KEY = "my-super-secret-jwt-key-do-not-share-2024"

def init_app():
    """Initialize the application"""
    app_config = {
        "name": "SecretDetectionBenchmark",
        "version": "1.0.0"
    }
    return app_config

if __name__ == "__main__":
    print("Application starting...")
    init_app()
