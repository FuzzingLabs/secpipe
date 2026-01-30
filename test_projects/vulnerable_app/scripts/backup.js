/**
 * Backup script with JavaScript security vulnerabilities
 */

// Hardcoded API keys and secrets
const API_KEY = "api_key_1234567890abcdefghijklmnopqrstuvwxyz";
const SECRET_KEY = "secret_1234567890abcdefghijklmnopqrstuvwxyz";
const MONGODB_URI = "mongodb://admin:password123@localhost:27017/mydb";
const REDIS_PASSWORD = "redis_password_123456";

// Firebase configuration with keys
const firebaseConfig = {
    apiKey: "AIzaSyDOCAbC123dEf456GhI789jKl01-MnO",
    authDomain: "myapp.firebaseapp.com",
    projectId: "myapp-12345",
    storageBucket: "myapp.appspot.com",
    messagingSenderId: "123456789",
    appId: "1:123456789:web:ab123cd456ef789gh012ij"
};

// Dangerous eval usage
function executeCode(userInput) {
    eval(userInput);  // Code injection vulnerability
}

// Dynamic function creation
function createFunction(code) {
    return new Function(code);  // Code injection vulnerability
}

// XSS vulnerabilities
function displayMessage(message) {
    document.body.innerHTML = message;  // XSS vulnerability
}

function updateContent(html) {
    document.getElementById('content').innerHTML = html;  // XSS vulnerability
}

// Insecure data handling
function processUserData(data) {
    document.write(data);  // XSS vulnerability
}

// Command injection via child_process
const { exec } = require('child_process');

function runCommand(userInput) {
    exec('ls ' + userInput, (error, stdout, stderr) => {  // Command injection
        console.log(stdout);
    });
}

// SQL injection in Node.js
function getUserData(userId) {
    const query = `SELECT * FROM users WHERE id = ${userId}`;  // SQL injection
    db.query(query);
}

// Path traversal
const fs = require('fs');

function readFile(filename) {
    return fs.readFileSync('../../../' + filename);  // Path traversal
}

// Insecure randomness
function generateToken() {
    return Math.random().toString(36);  // Weak randomness
}

// Hardcoded JWT secret
const jwt = require('jsonwebtoken');
const JWT_SECRET = 'my-super-secret-jwt-key';

function createToken(payload) {
    return jwt.sign(payload, JWT_SECRET);
}

// Bitcoin private key (example)
const BITCOIN_PRIVATE_KEY = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS";

// Ethereum private key
const ETH_PRIVATE_KEY = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef";

// AWS credentials in code
process.env.AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE";
process.env.AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY";