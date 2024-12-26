from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import cohere
from datetime import datetime, timedelta
import os
import jwt
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import tiktoken
import logging
from time import sleep  # For retry logic

# Logging Configuration
logging.basicConfig(level=logging.INFO)

# Initialize Flask App
app = Flask(__name__)

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Configuration
UPLOAD_FOLDER = "uploads"
LAWS_FOLDER = "HookeyMecher"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["ai_service"]
users_collection = db["users"]

# API Keys and Other Configs
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "your_default_cohere_api_key")
JWT_SECRET = os.environ.get("JWT_SECRET", "JWT_secret_key")
JWT_EXPIRATION_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", 30))
co = cohere.Client(COHERE_API_KEY)

# Helper Functions
def generate_embeddings_with_rate_handling(chunks, retries=3):
    for attempt in range(retries):
        try:
            return co.embed(texts=chunks).embeddings
        except Exception as e:
            if "rate limit exceeded" in str(e).lower():
                logging.warning("Rate limit exceeded. Waiting for 60 seconds before retrying.")
                sleep(60)
            else:
                logging.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                sleep(2 ** attempt)
    logging.error("All embedding generation attempts failed.")
    return []

def chunk_text(text, max_tokens=512):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    chunks, current_chunk = [], []

    for token in tokens:
        if len(current_chunk) + 1 > max_tokens:
            chunks.append(tokenizer.decode(current_chunk))
            current_chunk = []
        current_chunk.append(token)

    if current_chunk:
        chunks.append(tokenizer.decode(current_chunk))
    
    return [chunk for chunk in chunks if len(tokenizer.encode(chunk)) <= max_tokens]

def generate_token(email):
    expiration = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    return jwt.encode({"email": email, "exp": expiration}, JWT_SECRET, algorithm="HS256")

def decode_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["email"]
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def load_laws():
    laws = {}
    try:
        for filename in os.listdir(LAWS_FOLDER):
            if filename.endswith(".txt"):
                law_id = os.path.splitext(filename)[0].strip()
                with open(os.path.join(LAWS_FOLDER, filename), "r", encoding="utf-8") as file:
                    laws[law_id] = file.read()
    except Exception as e:
        app.logger.error(f"Error loading laws: {e}")
    return laws

@app.route("/api/sign-in", methods=["POST"])
def sign_in():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Invalid input"}), 400

    email, password = data["email"], data["password"]
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 400

    password_hash = generate_password_hash(password)
    users_collection.insert_one({"email": email, "password_hash": password_hash})
    return jsonify({"message": "Sign-up successful"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Invalid input"}), 400

    email, password = data["email"], data["password"]
    user = users_collection.find_one({"email": email})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = generate_token(email)
    return jsonify({"message": "Login successful", "token": token}), 200

@app.route("/api/contract-compliance", methods=["POST"])
def contract_compliance():
    try:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not decode_token(token):
            return jsonify({"error": "Invalid or missing token"}), 401

        if "file" not in request.files or not request.form.getlist("selected_laws"):
            return jsonify({"error": "File and selected laws required"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        with open(file_path, "rb") as f:
            file_content = f.read()
        user_content = file_content.decode("utf-8", errors="ignore")
        os.remove(file_path)

        selected_laws = request.form.getlist("selected_laws")
        laws = load_laws()
        compliance_results = []

        for law_id in selected_laws:
            if law_id not in laws:
                compliance_results.append({"law_id": law_id, "status": "Not Found"})
                continue

            user_chunks = chunk_text(user_content)
            law_chunks = chunk_text(laws[law_id])
            user_embeddings = generate_embeddings_with_rate_handling(user_chunks)
            law_embeddings = generate_embeddings_with_rate_handling(law_chunks)

            if not user_embeddings or not law_embeddings:
                compliance_results.append({"law_id": law_id, "status": "Error"})
                continue

            user_vector = np.mean(user_embeddings, axis=0)
            law_vector = np.mean(law_embeddings, axis=0)
            similarity = cosine_similarity([user_vector], [law_vector])[0][0]
            compliance_results.append({
                "law_id": law_id,
                "status": "Compliant" if similarity > 0.8 else "Non-Compliant",
                "details": f"Similarity score: {similarity:.2f}"
            })

        return jsonify({"result": compliance_results}), 200
    except Exception as e:
        app.logger.error(f"Error in contract_compliance: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>", methods=["GET"])
def serve_static_files(path):
    try:
        return send_from_directory(".", path)
    except Exception as e:
        app.logger.error(f"File not found: {path} - {e}")
        return make_response("File not found", 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
