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

COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "your_default_cohere_api_key")
JWT_SECRET = os.environ.get("JWT_SECRET", "JWT_secret_key")
JWT_EXPIRATION_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", 30))
co = cohere.Client(COHERE_API_KEY)

# Helper Functions
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
    """Load laws from the HookeyMecher directory."""
    laws = {}
    try:
        for filename in os.listdir(LAWS_FOLDER):
            if filename.endswith(".txt"):
                law_id = os.path.splitext(filename)[0].strip()
                file_path = os.path.join(LAWS_FOLDER, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        laws[law_id] = file.read()
                    app.logger.info(f"Successfully loaded law file: {filename}")
                except UnicodeDecodeError:
                    app.logger.error(f"Failed to decode file {filename}. Ensure it's UTF-8 encoded.")
                except Exception as e:
                    app.logger.error(f"Error reading file {filename}: {str(e)}")
        if laws:
            app.logger.info(f"Loaded law IDs: {list(laws.keys())}")
        else:
            app.logger.warning("No valid laws were loaded from the HookeyMecher directory.")
    except Exception as e:
        app.logger.error(f"Error loading laws from directory: {str(e)}")
    return laws

def chunk_text(text, max_tokens=512):
    """Split text into chunks of at most `max_tokens` tokens."""
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    chunks = []

    # Split tokens into chunks and verify lengths
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i:i + max_tokens]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunk_token_count = len(tokenizer.encode(chunk_text))  # Recalculate tokens after decoding

        if chunk_token_count > max_tokens:
            raise ValueError(f"Chunk exceeds max token limit with {chunk_token_count} tokens.")
        
        chunks.append(chunk_text)

    return chunks

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

@app.route("/api/contract-compliance", methods=["POST"])
def contract_compliance():
    try:
        # Authorization and file validation
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Authorization token is missing"}), 401

        token = token.replace("Bearer ", "")
        email = decode_token(token)
        if not email:
            return jsonify({"error": "Invalid or expired token"}), 401

        if "file" not in request.files or not request.form.getlist("selected_laws"):
            return jsonify({"error": "File and selected laws are required"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Read and decode the uploaded file
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
            try:
                user_content = file_content.decode("utf-8")
            except UnicodeDecodeError:
                user_content = file_content.decode("iso-8859-1")
        except Exception as e:
            app.logger.error(f"Failed to read file: {str(e)}")
            return jsonify({"error": f"Failed to read the uploaded file: {str(e)}"}), 500

        # Process laws and compliance check
        selected_laws = request.form.getlist("selected_laws")
        laws = load_laws()
        compliance_results = []

        for law_id in selected_laws:
            if law_id in laws:
                law_text = laws[law_id]
                try:
                    # Chunk the user content and law text
                    user_chunks = list(chunk_text(user_content, max_tokens=512))
                    law_chunks = list(chunk_text(law_text, max_tokens=512))

                    # Log the chunk sizes and token counts
                    app.logger.info(f"Number of user_chunks: {len(user_chunks)}")
                    app.logger.info(f"Number of law_chunks: {len(law_chunks)}")
                    for i, chunk in enumerate(user_chunks):
                        chunk_tokens = tiktoken.get_encoding("cl100k_base").encode(chunk)
                        app.logger.info(f"User chunk {i} - Tokens: {len(chunk_tokens)}")
                    for i, chunk in enumerate(law_chunks):
                        chunk_tokens = tiktoken.get_encoding("cl100k_base").encode(chunk)
                        app.logger.info(f"Law chunk {i} - Tokens: {len(chunk_tokens)}")

                    # Generate embeddings for all chunks
                    user_embeddings = co.embed(texts=user_chunks).embeddings
                    law_embeddings = co.embed(texts=law_chunks).embeddings

                    # Aggregate embeddings (e.g., by averaging)
                    user_vector = np.mean(user_embeddings, axis=0)
                    law_vector = np.mean(law_embeddings, axis=0)

                    # Compute cosine similarity
                    similarity = cosine_similarity(
                        [np.array(user_vector)],
                        [np.array(law_vector)]
                    )[0][0]

                    compliance_results.append({
                        "law_id": law_id,
                        "status": "Compliant" if similarity > 0.8 else "Non-Compliant",
                        "details": f"Similarity score: {similarity:.2f}"
                    })
                except Exception as e:
                    app.logger.error(f"Error comparing law {law_id}: {str(e)}")
                    compliance_results.append({
                        "law_id": law_id,
                        "status": "Error",
                        "details": f"Error during compliance check: {str(e)}"
                    })
            else:
                compliance_results.append({
                    "law_id": law_id,
                    "status": "Not Found",
                    "details": "Law not found in the system."
                })

        return jsonify({"result": compliance_results}), 200

    except Exception as e:
        app.logger.error(f"Unexpected error in contract_compliance: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

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
