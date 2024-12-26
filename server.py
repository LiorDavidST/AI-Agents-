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
import time

def generate_embeddings_with_retry(chunks, retries=3):
    for attempt in range(retries):
        try:
            return co.embed(texts=chunks).embeddings
        except Exception as e:
            logging.warning(f"Embedding generation attempt {attempt + 1} failed: {str(e)}")
            time.sleep(2 ** attempt)  # Exponential backoff
    logging.error("All embedding generation attempts failed.")
    return []


def chunk_text(text, max_tokens=512):
    """
    Split text into chunks of at most `max_tokens` tokens, ensuring no chunk exceeds the limit.

    Parameters:
        text (str): Input text to split.
        max_tokens (int): Maximum number of tokens per chunk.

    Returns:
        List[str]: List of text chunks.
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string.")
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError("`max_tokens` must be a positive integer.")

    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    total_tokens = len(tokens)

    # Log initial information
    logging.info(f"Chunking text of {total_tokens} tokens into chunks of max {max_tokens} tokens.")

    chunks = []
    current_chunk = []

    for i, token in enumerate(tokens):
        if len(current_chunk) + 1 > max_tokens:
            # Finalize the current chunk
            chunk_text = tokenizer.decode(current_chunk)
            chunk_size = len(tokenizer.encode(chunk_text))
            chunks.append(chunk_text)
            logging.debug(f"Chunk created with {chunk_size} tokens at index {i}.")
            current_chunk = []

        current_chunk.append(token)

    # Add any remaining tokens as the last chunk
    if current_chunk:
        chunk_text = tokenizer.decode(current_chunk)
        chunk_size = len(tokenizer.encode(chunk_text))
        chunks.append(chunk_text)
        logging.debug(f"Final chunk created with {chunk_size} tokens.")

    # Log summary of chunks
    for idx, chunk in enumerate(chunks):
        chunk_size = len(tokenizer.encode(chunk))
        if chunk_size > max_tokens:
            logging.error(f"Chunk {idx + 1} exceeds max_tokens: {chunk_size} tokens.")
        else:
            logging.info(f"Chunk {idx + 1} contains {chunk_size} tokens.")

    logging.info(f"Total chunks created: {len(chunks)}.")
    return chunks

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
def generate_embeddings(chunks):
    """
    Generate embeddings for a list of text chunks using Cohere's API.

    Parameters:
        chunks (List[str]): List of text chunks.

    Returns:
        List[np.ndarray]: List of embeddings for each chunk.
    """
    try:
        return co.embed(texts=chunks).embeddings
    except Exception as e:
        logging.error(f"Error generating embeddings: {str(e)}")
        return []

def generate_embeddings_with_retry(chunks, retries=3):
    """
    Generate embeddings with retry logic in case of transient errors.

    Parameters:
        chunks (List[str]): List of text chunks to generate embeddings for.
        retries (int): Number of retry attempts in case of failure.

    Returns:
        List[List[float]]: List of embeddings for each chunk.
    """
    for attempt in range(retries):
        try:
            return co.embed(texts=chunks).embeddings
        except Exception as e:
            logging.warning(f"Embedding generation attempt {attempt + 1} failed: {str(e)}")
            time.sleep(2 ** attempt)  # Exponential backoff
    logging.error("All embedding generation attempts failed.")
    return [] 
 
def chunk_text(text, max_tokens=512):
    """
    Split text into chunks of at most `max_tokens` tokens, ensuring no chunk exceeds the limit.

    Parameters:
        text (str): Input text to split.
        max_tokens (int): Maximum number of tokens per chunk.

    Returns:
        List[str]: List of text chunks.
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string.")
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError("`max_tokens` must be a positive integer.")

    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    chunks = []
    current_chunk = []

    for token in tokens:
        # Add the token to the current chunk
        if len(current_chunk) + 1 > max_tokens:
            # If adding the token exceeds the limit, finalize the current chunk
            chunks.append(tokenizer.decode(current_chunk))
            current_chunk = []
        current_chunk.append(token)

    # Add any remaining tokens as the last chunk
    if current_chunk:
        chunks.append(tokenizer.decode(current_chunk))

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
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)  # Ensure cleanup happens

        # Process laws and compliance check
        selected_laws = request.form.getlist("selected_laws")
        laws = load_laws()
        compliance_results = []

        for law_id in selected_laws:
            if law_id in laws:
                law_text = laws[law_id]
                try:
                    # Chunk the user content and law text, filtering out empty chunks
                    user_chunks = [chunk for chunk in chunk_text(user_content, max_tokens=512) if chunk.strip()]
                    law_chunks = [chunk for chunk in chunk_text(law_text, max_tokens=512) if chunk.strip()]

                    # Add debug logging for insights
                    app.logger.debug(f"Raw user text length: {len(user_content)}")
                    app.logger.debug(f"Raw law text length: {len(law_text)}")
                    app.logger.debug(f"First user chunk: {user_chunks[0] if user_chunks else 'N/A'}")

                    app.logger.info(f"Number of user_chunks: {len(user_chunks)}")
                    app.logger.info(f"Number of law_chunks: {len(law_chunks)}")

                    # Generate embeddings and validate
                    user_embeddings = generate_embeddings_with_retry(user_chunks)
                    law_embeddings = generate_embeddings_with_retry(law_chunks)
                    if not user_embeddings or not law_embeddings:
                        raise ValueError("Failed to generate embeddings.")

                    # Aggregate embeddings and compute similarity
                    user_vector = np.mean(user_embeddings, axis=0)
                    law_vector = np.mean(law_embeddings, axis=0)
                    similarity = cosine_similarity([user_vector], [law_vector])[0][0]

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
