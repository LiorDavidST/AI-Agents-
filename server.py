from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
import cohere
from datetime import datetime, timedelta
import pytz
import requests
import os
import jwt

app = Flask(__name__)

# Enable CORS with stricter policy
CORS(app, resources={r"/api/*": {"origins": ["https://ai-agents-1yi8.onrender.com"]}})

# Set a maximum upload size (e.g., 5MB)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['ai_service']
users_collection = db['users']

# API Keys
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "your_default_cohere_api_key")
JWT_SECRET = os.environ.get("JWT_SECRET", "JWT_secret_key")
JWT_EXPIRATION_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", 30))
co = cohere.Client(COHERE_API_KEY)

# Helper functions
def generate_token(email):
    """Generate a JWT token for the user."""
    expiration = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    return jwt.encode({"email": email, "exp": expiration}, JWT_SECRET, algorithm="HS256")

def decode_token(token):
    """Decode a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["email"]
    except jwt.ExpiredSignatureError:
        app.logger.info("Token has expired.")
        return None
    except jwt.InvalidTokenError:
        app.logger.info("Invalid token provided.")
        return None

# User Authentication Endpoints

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json
        if not data or "email" not in data or "password" not in data:
            app.logger.error("Invalid input: Missing email or password")
            return jsonify({"error": "Invalid input"}), 400

        email = data["email"]
        password = data["password"]
        app.logger.info(f"Login attempt with email: {email}")

        # Find user by email
        user = users_collection.find_one({"email": email})
        if not user:
            app.logger.warning(f"User not found: {email}")
            return jsonify({"error": "Invalid email or password"}), 401

        # Verify the password
        if check_password_hash(user["password_hash"], password):
            app.logger.info(f"Password verified for user: {email}")
            token = generate_token(email)
            app.logger.info(f"Generated token: {token}")
            return jsonify({"message": "Login successful", "token": token}), 200
        else:
            app.logger.warning(f"Password mismatch for user: {email}")
            return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e:
        app.logger.error(f"Error during login: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Invalid input"}), 400

    email = data["email"]
    password = data["password"]

    # Find user by email
    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # Verify the password
    if check_password_hash(user["password_hash"], password):
        token = generate_token(email)
        return jsonify({"message": "Login successful", "token": token}), 200
    else:
        return jsonify({"error": "Invalid email or password"}), 401

@app.route("/api/cohere-chat", methods=["POST"])
def cohere_chat():
    token = request.headers.get("Authorization")
    app.logger.info(f"Authorization Header: {token}")  # Log the Authorization header

    if not token:
        app.logger.info("Missing Authorization Header")
        return jsonify({"error": "Authorization token is missing"}), 401

    token = token.replace("Bearer ", "")  # Remove 'Bearer' prefix if present
    email = decode_token(token)
    app.logger.info(f"Decoded Email from Token: {email}")  # Log the decoded email

    if not email:
        app.logger.info("Invalid or Expired Token")
        return jsonify({"error": "Invalid or expired token"}), 401

    try:
        data = request.json
        if not data or "message" not in data:
            app.logger.info("Invalid Request Body")
            return jsonify({"error": "Invalid request. 'message' field is required."}), 400

        user_message = data["message"]
        app.logger.info(f"User Message: {user_message}")  # Log the user's message

        response = co.generate(
            model="command-xlarge-nightly",
            prompt=f"User: {user_message}\nAssistant:",
            max_tokens=150,
            temperature=0.7
        )
        reply = response.generations[0].text.strip()
        app.logger.info(f"AI Reply: {reply}")  # Log the AI's reply

        return jsonify({"reply": reply})
    except Exception as e:
        app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# Static File Serving
@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>", methods=["GET"])
def serve_static_files(path):
    try:
        return send_from_directory(".", path)
    except Exception as e:
        app.logger.error(f"File not found: {path} - {str(e)}")
        return make_response(f"File not found: {path}", 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
