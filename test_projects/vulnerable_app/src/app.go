package main

import (
    "database/sql"
    "fmt"
    "os/exec"
    "net/http"
)

// Hardcoded credentials and secrets
const (
    DBPassword = "GoDBPassword123!"
    APIKey = "api_key_golang_1234567890abcdefghij"
    JWTSecret = "super_secret_jwt_key_golang"
    AWSAccessKey = "AKIAIOSFODNN7EXAMPLE"
    AWSSecretKey = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    StripeAPIKey = "sk_test_4eC39HqLyjWDarjtT1zdp7dc"
    SlackWebhook = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
)

// Private keys
var privateKey = `-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA4f5wg5l2iFFGH3FakeKeyForTesting1234567890
-----END RSA PRIVATE KEY-----`

type App struct {
    db *sql.DB
}

// SQL Injection vulnerability
func (a *App) GetUser(userID string) {
    query := fmt.Sprintf("SELECT * FROM users WHERE id = %s", userID) // SQL injection
    rows, _ := a.db.Query(query)
    defer rows.Close()
}

// Another SQL injection
func (a *App) SearchProducts(search string) {
    query := "SELECT * FROM products WHERE name LIKE '%" + search + "%'" // SQL injection
    a.db.Query(query)
}

// Command injection
func ExecuteCommand(input string) {
    cmd := exec.Command("sh", "-c", "echo "+input) // Command injection
    cmd.Run()
}

// Path traversal
func ReadFile(filename string) {
    path := "/var/www/uploads/" + filename // Path traversal vulnerability
    // Read file without validation
}

// Hardcoded MongoDB connection string
const MongoDBURI = "mongodb://admin:password123@localhost:27017/mydb"

// Bitcoin private key
const BitcoinPrivateKey = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"

// Ethereum private key
const EthereumPrivateKey = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f3e2e1a2e4567890abc"

// More API keys
var (
    TwilioAccountSID = "AC1234567890abcdefghijklmnopqrstuv"
    TwilioAuthToken = "1234567890abcdefghijklmnopqrstuv"
    SendGridAPIKey = "SG.1234567890.abcdefghijklmnopqrstuvwxyz"
    GitHubToken = "github_pat_11AAAAAAA_1234567890abcdefghijklmnop"
)

func main() {
    // Insecure HTTP server
    http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        userInput := r.URL.Query().Get("input")
        // No input validation
        fmt.Fprintf(w, "User input: %s", userInput) // Potential XSS
    })
    http.ListenAndServe(":8080", nil)
}