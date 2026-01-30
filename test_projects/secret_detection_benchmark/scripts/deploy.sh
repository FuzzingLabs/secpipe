#!/bin/bash
# Deployment script

# MEDIUM SECRET #14: Secret in environment variable export
export SECRET_API_KEY="sk_prod_1234567890abcdefghijklmnopqrstuvwxyz"

echo "Deploying application..."

# MEDIUM SECRET #15: URL-encoded secret in connection string (backup comment)
# backup_connection="mysql://admin:MyP%40ssw0rd%21@db.example.com:3306/prod"

deploy_app() {
    echo "Deployment complete"
}

deploy_app
