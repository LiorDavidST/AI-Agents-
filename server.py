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

# Define constants
MAX_TOKENS = 512  # Maximum tokens per chunk for processing

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
    
def validate_chunk_length(chunks, max_tokens):
    """
    Validate that all chunks are within the maximum token limit.

    Parameters:
        chunks (list of str): The list of text chunks to validate.
        max_tokens (int): The maximum allowed tokens per chunk.

    Returns:
        list: A list of validated chunks, with oversized chunks truncated if necessary.

    Raises:
        ValueError: If all chunks exceed the max token limit.
    """
    tokenizer = tiktoken.get_encoding("cl100k_base")
    validated_chunks = []
    all_chunks_invalid = True

    for i, chunk in enumerate(chunks):
        chunk_tokens = tokenizer.encode(chunk)
        chunk_length = len(chunk_tokens)
        app.logger.debug(f"Validating chunk {i}: {chunk_length} tokens.")  # Debug log

        if chunk_length > max_tokens:
            truncated_chunk = tokenizer.decode(chunk_tokens[:max_tokens])
            app.logger.warning(f"Chunk {i} truncated to {max_tokens} tokens (original: {chunk_length}).")
            validated_chunks.append(truncated_chunk)
        else:
            validated_chunks.append(chunk)
            all_chunks_invalid = False  # At least one valid chunk

    if all_chunks_invalid:
        app.logger.error("All chunks exceed the maximum token limit after validation.")
        raise ValueError("All chunks exceed the maximum token limit.")

    return validated_chunks

def truncate_chunks(chunks, max_tokens):
    """
    Truncate each chunk to ensure it is within the token limit.

    Parameters:
        chunks (list of str): The list of text chunks.
        max_tokens (int): Maximum tokens allowed per chunk.

    Returns:
        list: A list of valid, truncated chunks.
    """
    tokenizer = tiktoken.get_encoding("cl100k_base")
    truncated_chunks = []
    for i, chunk in enumerate(chunks):
        tokens = tokenizer.encode(chunk)
        if len(tokens) > max_tokens:
            truncated_chunk = tokenizer.decode(tokens[:max_tokens])
            app.logger.warning(f"Chunk {i} truncated to {max_tokens} tokens (original: {len(tokens)}).")
            truncated_chunks.append(truncated_chunk)
        else:
            truncated_chunks.append(chunk)
    return truncated_chunks


def chunk_text(text, max_tokens):
    """
    Split text into chunks of at most `max_tokens` tokens, ensuring no chunk exceeds the limit.
    Handles specific language encodings, including Hebrew.
    """
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)  # Encode the text into tokens

    if not tokens:
        app.logger.error("Text could not be tokenized. Ensure the input is valid.")
        return []

    chunks = []
    current_chunk = []

    # Create chunks strictly adhering to max_tokens limit
    for token in tokens:
        if len(current_chunk) >= max_tokens:  # Check if the current chunk is full
            chunks.append(current_chunk)  # Append the tokenized chunk
            current_chunk = []

        current_chunk.append(token)

    if current_chunk:
        chunks.append(current_chunk)  # Add remaining tokens

    # Decode and truncate chunks if necessary
    valid_chunks = []
    for i, chunk_tokens in enumerate(chunks):
        if len(chunk_tokens) > max_tokens:
            truncated_chunk_tokens = chunk_tokens[:max_tokens]
            valid_chunks.append(tokenizer.decode(truncated_chunk_tokens))
            app.logger.warning(f"Chunk {i} truncated to {max_tokens} tokens (original: {len(chunk_tokens)}).")
        else:
            valid_chunks.append(tokenizer.decode(chunk_tokens))

    # Debug logging for chunk details
    for i, chunk in enumerate(valid_chunks):
        chunk_length = len(tokenizer.encode(chunk))
        app.logger.debug(f"Chunk {i} has {chunk_length} tokens.")

    # Handle empty valid chunks case
    if not valid_chunks:
        app.logger.error("All chunks are empty after processing. This may be due to language-specific encoding issues.")
        return []

    return valid_chunks



    
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
                    user_content = file_content.decode("utf-8")  # Hebrew typically uses UTF-8
                except UnicodeDecodeError:
                    user_content = file_content.decode("iso-8859-8")  # Alternative Hebrew encoding
        except Exception as e:
            app.logger.error(f"Failed to read file: {str(e)}")
            return jsonify({"error": f"Failed to read the uploaded file: {str(e)}"}), 500
        finally:
            # Ensure the file is removed after processing
            if os.path.exists(file_path):
                os.remove(file_path)

        # Process laws and compliance check
        selected_laws = request.form.getlist("selected_laws")
        laws = load_laws()
        compliance_results = []

        for law_id in selected_laws:
            if law_id in laws:
                law_text = laws[law_id]
                try:
                    # Chunk the user content and law text
                    user_chunks = chunk_text(user_content, MAX_TOKENS)
                    law_chunks = chunk_text(law_text, MAX_TOKENS)

                    # Check if user_chunks is empty
                    if not user_chunks:
                        return jsonify({
                            "error": "The uploaded text could not be processed. It may contain excessively long text sections or unsupported encoding."
                        }), 400

                    # Log chunk details for debugging
                    app.logger.info(f"Number of user_chunks: {len(user_chunks)}")
                    app.logger.info(f"Number of law_chunks: {len(law_chunks)}")

                    # Generate embeddings for all chunks
                    user_embeddings = co.embed(texts=user_chunks).embeddings
                    law_embeddings = co.embed(texts=law_chunks).embeddings

                    # Aggregate embeddings
                    user_vector = np.mean(user_embeddings, axis=0)
                    law_vector = np.mean(law_embeddings, axis=0)

                    # Compute cosine similarity
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
