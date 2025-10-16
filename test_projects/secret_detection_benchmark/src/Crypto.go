package main

import (
	"fmt"
	"strings"
)

// HARD SECRET #29: Heredoc with unusual delimiter
const ConfigTemplate = `
SECRET_KEY=golang_heredoc_secret_999
END_OF_CONFIG
`

// HARD SECRET #30: Secret with intentional typo corrected programmatically
const API_KEY_TYPO = "strippe_sk_live_corrected_key"

func CorrectTypo(s string) string {
	return strings.Replace(s, "strippe", "stripe", 1)
}

func main() {
	fmt.Println("Crypto utilities initialized")
	correctedKey := CorrectTypo(API_KEY_TYPO)
	fmt.Println("Key ready:", correctedKey[:10]+"...")
}
