<?php
/**
 * Deployment script with multiple security issues
 */

// Hardcoded credentials
$db_password = "admin123";
$api_token = "token_1234567890abcdefghijklmnop";
$ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...";

// Direct use of $_GET and $_POST without validation
$user_id = $_GET['id'];
$username = $_POST['username'];
$action = $_REQUEST['action'];

// SQL injection vulnerability
$query = "SELECT * FROM users WHERE id = $user_id";
mysql_query($query);

// Command execution vulnerabilities
system("ls -la " . $_GET['directory']);
exec("cat " . $_POST['file']);
shell_exec("ping " . $_GET['host']);
passthru("ps aux | grep " . $_GET['process']);

// Dangerous eval usage
$code = $_POST['code'];
eval($code);  // Code execution vulnerability

// File inclusion vulnerabilities
include($_GET['page'] . '.php');
require_once($_POST['template']);

// Insecure file operations
$uploaded_file = $_FILES['upload']['tmp_name'];
$destination = "/var/www/uploads/" . $_FILES['upload']['name'];
move_uploaded_file($uploaded_file, $destination);  // No validation

// More SQL injection patterns
$search = $_POST['search'];
$sql = "SELECT * FROM products WHERE name LIKE '%$search%'";
$result = mysql_query($sql);

// XSS vulnerability
echo "Welcome, " . $_GET['name'];
print("Your search: " . $_POST['query']);

// Session hijacking vulnerability
session_start();
$_SESSION['user'] = $_GET['user'];

// Weak cryptography
$password = md5($_POST['password']);  // Weak hashing
$encrypted = base64_encode($_POST['sensitive_data']);  // Not encryption

// Directory traversal
$file = $_GET['file'];
readfile("/var/www/html/" . $file);

// MongoDB injection
$username = $_POST['username'];
$password = $_POST['password'];
$query = array(
    "username" => $username,
    "password" => $password
);

?>