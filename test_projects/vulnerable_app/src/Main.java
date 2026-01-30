import java.sql.*;
import java.io.*;
import java.util.*;

public class Main {
    // Hardcoded database credentials
    private static final String DB_URL = "jdbc:mysql://localhost:3306/production";
    private static final String DB_USER = "admin";
    private static final String DB_PASSWORD = "JavaDBPassword123!";

    // API Keys
    private static final String API_KEY = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz";
    private static final String SECRET_TOKEN = "secret_token_abcdef1234567890";
    private static final String AWS_ACCESS = "AKIAIOSFODNN7EXAMPLE";
    private static final String AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY";

    public class VulnerableApp {

        // SQL Injection vulnerability
        public void getUserById(String userId) throws SQLException {
            Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD);
            Statement stmt = conn.createStatement();
            String query = "SELECT * FROM users WHERE id = " + userId; // SQL injection
            ResultSet rs = stmt.executeQuery(query);
        }

        // Another SQL injection with string concatenation
        public void searchProducts(String searchTerm) throws SQLException {
            String query = "SELECT * FROM products WHERE name LIKE '%" + searchTerm + "%'";
            // Vulnerable to SQL injection
        }

        // Command injection vulnerability
        public void executeCommand(String filename) throws IOException {
            Runtime.getRuntime().exec("cat " + filename); // Command injection
        }

        // Path traversal vulnerability
        public void readFile(String filename) throws IOException {
            File file = new File("/var/www/uploads/" + filename); // Path traversal
            FileInputStream fis = new FileInputStream(file);
        }

        // XXE vulnerability
        public void parseXML(String xmlInput) {
            // XML parsing without disabling external entities
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            // Vulnerable to XXE attacks
        }

        // Insecure deserialization
        public Object deserialize(byte[] data) throws Exception {
            ByteArrayInputStream bis = new ByteArrayInputStream(data);
            ObjectInputStream ois = new ObjectInputStream(bis);
            return ois.readObject(); // Insecure deserialization
        }

        // Weak cryptography
        public String hashPassword(String password) {
            MessageDigest md = MessageDigest.getInstance("MD5"); // Weak hashing
            return new String(md.digest(password.getBytes()));
        }

        // Hardcoded encryption key
        private static final String ENCRYPTION_KEY = "MySecretEncryptionKey123";

        // LDAP injection
        public void authenticateUser(String username, String password) {
            String filter = "(uid=" + username + ")"; // LDAP injection
            // Vulnerable LDAP query
        }
    }

    // More hardcoded secrets
    private static final String STRIPE_KEY = "sk_live_4eC39HqLyjWDarjtT1zdp7dc";
    private static final String GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz";
    private static final String PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQ...";
}