-- Database initialization script

CREATE DATABASE prod_db;

-- MEDIUM SECRET #18: Secret in SQL comment
-- Connection string: postgresql://admin:Pr0dDB_S3cr3t_P@ss@db.prod.example.com:5432/prod_db

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL
);

-- Insert test data
INSERT INTO users (username, email) VALUES ('admin', 'admin@example.com');
