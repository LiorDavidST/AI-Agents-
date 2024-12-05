from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import cohere
from datetime import datetime, timedelta
import pytz
import requests
import os
import jwt

app = Flask(__name__)

# Enable CORS with enhanced configuration
CORS(app, resources={r"/api/*": {"origins": ["https://ai-agents-1yi8.onrender.com"]}},
     supports_credentials=True,  # Allow credentials if needed
     expose_headers=["Authorization"],  # Allow Authorization header in responses
     allow_headers=["Authorization", "Content-Type"])  # Explicitly allow Authorization header

# Set a maximum upload size (e.g., 5MB)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['ai_service']
users_collection = db['users']
reference_documents_collection = db['reference_documents']

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

@app.route("/api/sign-in", methods=["POST"])
def sign_in():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Invalid input"}), 400

    email = data["email"]
    password = data["password"]

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if users_collection.find_one({"email": email}):
        return jsonify({"error": f"The email '{email}' is already registered. Please log in or use a different email."}), 400

    password_hash = generate_password_hash(password)
    users_collection.insert_one({"email": email, "password_hash": password_hash})
    return jsonify({"message": "Sign-up successful"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Invalid input"}), 400

    email = data["email"]
    password = data["password"]

    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    if check_password_hash(user["password_hash"], password):
        token = generate_token(email)
        return jsonify({"message": "Login successful", "token": token}), 200
    else:
        return jsonify({"error": "Invalid email or password"}), 401

@app.route("/api/cohere-chat", methods=["POST"])
def cohere_chat():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token is missing"}), 401

    token = token.replace("Bearer ", "")
    email = decode_token(token)
    if not email:
        return jsonify({"error": "Invalid or expired token"}), 401

    try:
        data = request.json
        if not data or "message" not in data:
            return jsonify({"error": "Invalid request. 'message' field is required."}), 400

        user_message = data["message"]
        response = co.generate(
            model="command-xlarge-nightly",
            prompt=f"User: {user_message}\nAssistant:",
            max_tokens=150,
            temperature=0.7
        )
        reply = response.generations[0].text.strip()
        return jsonify({"reply": reply})
    except Exception as e:
        app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/api/contract-compliance", methods=["POST"])
def contract_compliance():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token is missing"}), 401

    token = token.replace("Bearer ", "")
    email = decode_token(token)
    if not email:
        return jsonify({"error": "Invalid or expired token"}), 401

    if "file" not in request.files:
        return jsonify({"error": "File is required for compliance check"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    # Dummy compliance logic for now
    compliance_result = {"status": "Compliant", "details": "File matches reference template."}
    return jsonify({"result": compliance_result}), 200

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
