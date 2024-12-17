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
        "action": "parse",  # שינוי הפעולה ל-parse
        "page": law_title,  # שימוש בשם החוק
        "prop": "text",  # שליפת התוכן בפורמט HTML
        "format": "json",
    }
    try:
        response = requests.get(MEDIAWIKI_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Log the full response for debugging
        app.logger.debug(f"MediaWiki response for '{law_title}': {data}")

        # שליפת ה-HTML מהשדה text
        html_content = data.get("parse", {}).get("text", {}).get("*", "")
        if not html_content:
            app.logger.warning(f"No content found for law title: {law_title}")
            return ""

        # שימוש ב-BeautifulSoup לניקוי ה-HTML
        soup = BeautifulSoup(html_content, "html.parser")
        law_text = soup.get_text(separator="\n", strip=True)

        return law_text
    except requests.RequestException as e:
        app.logger.error(f"Error fetching law '{law_title}': {str(e)}")
        return ""  # Return an empty string to prevent crashes

def chunk_text(text, max_tokens=512):
    """Split text into chunks of at most `max_tokens` tokens."""
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    chunks = []
    current_chunk = []

    for token in tokens:
        current_chunk.append(token)
        if len(current_chunk) >= max_tokens:
            chunks.append(tokenizer.decode(current_chunk))
            current_chunk = []

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

@app.route("/api/predefined-laws", methods=["GET"])
def get_predefined_laws():
    """Fetch predefined laws from MediaWiki and return as JSON."""
    predefined_laws = {
        "1": "חוק_המכר_(דירות)",
        "2": "חוק מכר דירות הבטחת השקעה 1974",
        "3": "חוק מכר דירות הבטחת השקעה תיקון מספר 9",
        "4": "תקנות המכר (דירות) (הבטחת השקעות של רוכשי דירות) (סייג לתשלומים על חשבון מחיר דירה), 1975",
    }
    laws = {}
    for law_id, law_title in predefined_laws.items():
        law_content = fetch_law_from_mediawiki(law_title)
        if law_content:
            laws[law_id] = law_content
        else:
            app.logger.warning(f"Failed to fetch content for law: {law_title}")
    return jsonify({"laws": laws}), 200

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
                    "status": "Error",
                    "details": "Law content is empty or invalid."
                })
                continue  # Skip processing this law

            try:
                # Split texts into chunks
                user_chunks = chunk_text(user_content, max_tokens=512)
                law_chunks = chunk_text(law_text, max_tokens=512)

                # Generate embeddings for chunks
                user_embeddings = co.embed(texts=user_chunks).embeddings
                law_embeddings = co.embed(texts=law_chunks).embeddings

                # Compute mean vectors
                user_vector = np.mean(user_embeddings, axis=0)
                law_vector = np.mean(law_embeddings, axis=0)

                # Compute cosine similarity
                similarity = cosine_similarity([user_vector], [law_vector])[0][0]

                # Append result
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

        return jsonify({"result": compliance_results}), 200
    except Exception as e:
        app.logger.error(f"Unexpected error in contract_compliance: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
        
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