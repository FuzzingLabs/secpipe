# Ruby file with security vulnerabilities

require 'yaml'
require 'json'

# Hardcoded API credentials
TWITTER_API_KEY = "1234567890abcdefghijklmnopqrstuvw"
TWITTER_API_SECRET = "abcdefghijklmnopqrstuvwxyz1234567890abcdefghijk"
FACEBOOK_APP_ID = "1234567890123456"
FACEBOOK_APP_SECRET = "abcdef1234567890abcdef1234567890"

class SecurityUtils
  # Command injection vulnerability
  def run_system_command(user_input)
    system("echo #{user_input}")  # Command injection
  end

  # Another command injection
  def process_file(filename)
    `cat #{filename}`  # Command injection via backticks
  end

  # SQL injection in Ruby
  def find_user(id)
    query = "SELECT * FROM users WHERE id = #{id}"  # SQL injection
    ActiveRecord::Base.connection.execute(query)
  end

  # Dangerous eval
  def evaluate_expression(expr)
    eval(expr)  # Code injection vulnerability
  end

  # YAML deserialization vulnerability
  def load_config(yaml_string)
    YAML.load(yaml_string)  # Unsafe deserialization
  end

  # Mass assignment vulnerability
  def update_user(params)
    user = User.find(params[:id])
    user.update_attributes(params)  # Mass assignment
  end

  # File operation without validation
  def read_file(path)
    File.read("../../uploads/#{path}")  # Path traversal
  end

  # Weak password hashing
  def hash_password(password)
    Digest::MD5.hexdigest(password)  # Weak hashing algorithm
  end

  # Insecure random
  def generate_token
    rand(999999).to_s  # Predictable randomness
  end
end

# More credentials
DATABASE_PASSWORD = "ruby_db_password_123"
REDIS_PASSWORD = "redis_cache_password_456"
ELASTICSEARCH_API_KEY = "elastic_api_key_789xyz"