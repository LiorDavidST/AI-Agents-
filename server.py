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
import requests
import urllib.parse
from bs4 import BeautifulSoup
import time

app = Flask(__name__, static_folder='.', static_url_path='')  # Serve static files

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Configuration
UPLOAD_FOLDER = "uploads"
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

# External API Configuration
MEDIAWIKI_API_URL = "https://he.wikisource.org/w/api.php"

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

from bs4 import BeautifulSoup

def fetch_law_from_mediawiki(law_title):
    """Fetch the content of a law from MediaWiki API by title."""
    params = {
        "action": "parse",  # API action to parse a page
        "page": law_title,  # Law title to fetch
        "prop": "text",     # Retrieve content in HTML format
        "format": "json",
    }
    try:
        # Fetch the law from MediaWiki API
        response = requests.get(MEDIAWIKI_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Log the raw API response for debugging
        app.logger.debug(f"MediaWiki response for '{law_title}': {data}")

        # Extract HTML content from the response
        html_content = data.get("parse", {}).get("text", {}).get("*", "")
        if not html_content:
            app.logger.warning(f"No content found for law title: {law_title}")
            return ""

        # Clean the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        law_text = soup.get_text(separator="\n", strip=True)

        # Validate the size of the retrieved content
        token_count = len(tiktoken.get_encoding("cl100k_base").encode(law_text))
        if token_count > 5000:  # Arbitrary size limit for validation
            app.logger.warning(f"Retrieved law text for '{law_title}' is too long ({token_count} tokens). Truncating.")

            # Truncate the text to 5000 tokens
            tokens = tiktoken.get_encoding("cl100k_base").encode(law_text)[:5000]
            law_text = tiktoken.get_encoding("cl100k_base").decode(tokens)
            app.logger.debug(f"Truncated law text to 5000 tokens.")

        return law_text

    except requests.RequestException as e:
        app.logger.error(f"Error fetching law '{law_title}': {str(e)}")
        return ""  # Return an empty string to prevent crashes

    except Exception as e:
        app.logger.error(f"Unexpected error processing law '{law_title}': {str(e)}")
        return ""  # Handle unexpected errors gracefully

def chunk_text(text, max_tokens=512, max_total_tokens=20000):
    """Split text into chunks with a strict limit on max tokens and truncate if necessary."""
    tokenizer = tiktoken.get_encoding("cl100k_base")

    # Handle empty input text
    if not text.strip():
        app.logger.debug("Input text is empty. Returning no chunks.")
        return []

    # Encode the input text into tokens
    tokens = tokenizer.encode(text)
    total_token_count = len(tokens)

    # Truncate tokens if they exceed the maximum allowed
    if total_token_count > max_total_tokens:
        app.logger.warning(f"Input text exceeds {max_total_tokens} tokens. Truncating to {max_total_tokens} tokens.")
        tokens = tokens[:max_total_tokens]
        total_token_count = len(tokens)

    # Log the total number of tokens after truncation
    app.logger.debug(f"Total tokens after truncation (if applied): {total_token_count}")

    # Process tokens in slices of max_tokens size
    chunks = []
    for i in range(0, total_token_count, max_tokens):
        chunk = tokens[i:i + max_tokens]
        decoded_chunk = tokenizer.decode(chunk)

        # Revalidate and split oversized chunks
        token_count = len(tokenizer.encode(decoded_chunk))
        while token_count > max_tokens:
            app.logger.warning(f"Chunk exceeds {max_tokens} tokens. Splitting further.")
            midpoint = len(decoded_chunk) // 2
            chunk_a = decoded_chunk[:midpoint]
            chunk_b = decoded_chunk[midpoint:]
            chunks.append(chunk_a)
            decoded_chunk = chunk_b
            token_count = len(tokenizer.encode(decoded_chunk))

        # Append the final valid chunk
        chunks.append(decoded_chunk)

    # Log the details of generated chunks
    app.logger.debug(f"Generated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        app.logger.debug(f"  Chunk {i + 1}: {len(tokenizer.encode(chunk))} tokens")

    return chunks



def batch_embeddings(chunks, batch_size=5):
    """Generate embeddings in batches with validation and rate limiting."""
    embeddings = []
    tokenizer = tiktoken.get_encoding("cl100k_base")

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        validated_batch = []

        for chunk in batch:
            token_count = len(tokenizer.encode(chunk))
            if token_count > 512:
                app.logger.error(f"Chunk exceeds 512 tokens and will be skipped: {token_count} tokens")
            else:
                validated_batch.append(chunk)

        if not validated_batch:
            app.logger.warning(f"All chunks in batch {i // batch_size} are invalid.")
            continue

        try:
            response = co.embed(texts=validated_batch).embeddings
            embeddings.extend(response)
        except Exception as e:
            app.logger.error(f"Error embedding batch {i // batch_size}: {str(e)}")

        # Rate limiting: Add a delay between batches
        time.sleep(1.5)  # Adjust based on API rate limits

    return embeddings
  
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

@app.route("/api/predefined-laws", methods=["GET"])
def get_predefined_laws():
    """Return predefined law titles."""
    predefined_laws = {
        "1": "חוק המכר (דירות)",
        "2": "חוק מכר דירות הבטחת השקעה 1974",
        "3": "חוק מכר דירות הבטחת השקעה תיקון מספר 9",
        "4": "תקנות המכר (דירות) (הבטחת השקעות של רוכשי דירות) (סייג לתשלומים על חשבון מחיר דירה), 1975",
    }
    return jsonify(predefined_laws), 200

@app.route("/api/fetch-law-text", methods=["POST"])
def fetch_law_text():
    """Fetch the full law text by ID."""
    data = request.json
    if "law_id" not in data:
        return jsonify({"error": "law_id is required"}), 400

    law_id = data["law_id"]
    predefined_laws = {
        "1": "חוק_המכר_(דירות)",
        "2": "חוק מכר דירות הבטחת השקעה 1974",
        "3": "חוק מכר דירות הבטחת השקעה תיקון מספר 9",
        "4": "תקנות המכר (דירות) (הבטחת השקעות של רוכשי דירות) (סייג לתשלומים על חשבון מחיר דירה), 1975",
    }

    if law_id not in predefined_laws:
        return jsonify({"error": "Invalid law ID"}), 400

    law_title = predefined_laws[law_id]
    law_text = fetch_law_from_mediawiki(law_title)

    if not law_text:
        return jsonify({"error": "Unable to fetch law text"}), 500

    return jsonify({"law_id": law_id, "law_title": law_title, "law_text": law_text}), 200


@app.route("/api/contract-compliance", methods=["POST"])
def contract_compliance():
    """Handle contract compliance checks."""
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
        with open(file_path, "rb") as f:
            file_content = f.read()
        user_content = file_content.decode("utf-8", errors="ignore")

        # Process laws and compliance check
        selected_laws = request.form.getlist("selected_laws")
        predefined_laws = {
            "1": "חוק_המכר_(דירות)",
            "2": "חוק מכר דירות הבטחת השקעה 1974",
            "3": "חוק מכר דירות הבטחת השקעה תיקון מספר 9",
            "4": "תקנות המכר (דירות) (הבטחת השקעות של רוכשי דירות) (סייג לתשלומים על חשבון מחיר דירה), 1975",
        }
        laws = {law_id: fetch_law_from_mediawiki(predefined_laws[law_id])
                for law_id in selected_laws if law_id in predefined_laws}

        compliance_results = []

        # Compare each law to user content
        for law_id, law_text in laws.items():
            if not isinstance(law_text, str) or not law_text.strip():
                compliance_results.append({
                    "law_id": law_id,
                    "law_title": predefined_laws[law_id],
                    "status": "Error",
                    "similarity_score": "N/A",
                    "details": "Law content is empty or invalid."
                })
                continue  # Skip processing this law

            try:
                # Split texts into chunks
                user_chunks = chunk_text(user_content, max_tokens=500)
                law_chunks = chunk_text(law_text, max_tokens=500)

                # Generate embeddings with batching
                user_embeddings = batch_embeddings(user_chunks, batch_size=10)
                law_embeddings = batch_embeddings(law_chunks, batch_size=10)

                # Compute mean vectors
                user_vector = np.mean(user_embeddings, axis=0) if user_embeddings else None
                law_vector = np.mean(law_embeddings, axis=0) if law_embeddings else None

                # Compute cosine similarity
                similarity = cosine_similarity([user_vector], [law_vector])[0][0]

                # Append result
                compliance_results.append({
                    "law_id": law_id,
                    "law_title": predefined_laws[law_id],
                    "status": "Compliant" if similarity > 0.8 else "Non-Compliant",
                    "similarity_score": f"{similarity:.2f}",
                })
            except Exception as e:
                app.logger.error(f"Error comparing law {law_id}: {str(e)}")
                compliance_results.append({
                    "law_id": law_id,
                    "law_title": predefined_laws[law_id],
                    "status": "Error",
                    "similarity_score": "N/A",
                    "details": f"Error during compliance check: {str(e)}"
                })

        # Create HTML table
        html_table = """
        <table border="1">
            <tr>
                <th>Law ID</th>
                <th>Law Title</th>
                <th>Status</th>
                <th>Similarity Score</th>
            </tr>
        """
        for result in compliance_results:
            html_table += f"""
            <tr>
                <td>{result['law_id']}</td>
                <td>{result['law_title']}</td>
                <td>{result['status']}</td>
                <td>{result['similarity_score']}</td>
            </tr>
            """
        html_table += "</table>"

        return html_table, 200

    except Exception as e:
        app.logger.error(f"Unexpected error in contract_compliance: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

    finally:
        # Ensure the uploaded file is cleaned up
        if os.path.exists(file_path):
            os.remove(file_path)

@app.route("/", methods=["GET"])
def serve_index():
    """Serve the main index.html file."""
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>", methods=["GET"])
def serve_static_files(path):
    """Serve other static files."""
    try:
        return send_from_directory(app.static_folder, path)
    except Exception as e:
        app.logger.error(f"File not found: {path} - {str(e)}")
        return make_response(f"File not found: {path}", 404)

# Main entry point
if __name__ == "__main__":
    # Bind to dynamic PORT for Render deployment or default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)