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

app = Flask(__name__)

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Configuration
UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"
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

def fetch_law_from_mediawiki(law_title):
    """
    Fetches the content of a law from MediaWiki API by title.
    """
    API_ENDPOINT = "https://he.wikisource.org/w/api.php"
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": law_title,
        "rvslots": "*",
        "rvprop": "content",
        "format": "json"
    }
    try:
        response = requests.get(API_ENDPOINT, params=params)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_content in pages.items():
            if "revisions" in page_content:
                return page_content["revisions"][0]["slots"]["main"]["*"]
        return None
    except requests.RequestException as e:
        app.logger.error(f"Error fetching law {law_title}: {str(e)}")
        return None

def load_laws(selected_laws):
    """Load laws dynamically from MediaWiki API."""
    laws = {}
    for law_id, law_title in selected_laws.items():
        law_content = fetch_law_from_mediawiki(law_title)
        if law_content:
            laws[law_id] = law_content
        else:
            app.logger.warning(f"Failed to load law: {law_title}")
    return laws

@app.route("/api/predefined-laws", methods=["GET"])
def get_predefined_laws():
    """API endpoint to retrieve predefined laws."""
    predefined_laws = {
        "1": "חוק מכר דירות 1973",
        "2": "חוק מכר דירות הבטחת השקעה 1974",
        "3": "חוק מכר דירות הבטחת השקעה תיקון מספר 9",
        "4": "תקנות המכר (דירות) (הבטחת השקעות של רוכשי דירות) (סייג לתשלומים על חשבון מחיר דירה), -1975",
    }
    return jsonify({"laws": predefined_laws}), 200

@app.route("/api/contract-compliance", methods=["POST"])
def contract_compliance():
    """Handles contract compliance checking."""
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
        selected_law_ids = request.form.getlist("selected_laws")
        predefined_laws = {
            "1": "חוק מכר דירות 1973",
            "2": "חוק מכר דירות הבטחת השקעה 1974",
            "3": "חוק מכר דירות הבטחת השקעה תיקון מספר 9",
            "4": "תקנות המכר (דירות) (הבטחת השקעות של רוכשי דירות) (סייג לתשלומים על חשבון מחיר דירה), -1975",
        }
        selected_laws = {law_id: predefined_laws[law_id] for law_id in selected_law_ids if law_id in predefined_laws}
        laws = load_laws(selected_laws)
        compliance_results = []

        for law_id, law_text in laws.items():
            try:
                # Placeholder: Add logic for text comparison or compliance checks here.
                compliance_results.append({
                    "law_id": law_id,
                    "status": "Compliant",
                    "details": "Example compliance check passed."
                })
            except Exception as e:
                compliance_results.append({
                    "law_id": law_id,
                    "status": "Error",
                    "details": str(e)
                })

        return jsonify({"result": compliance_results}), 200
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route("/", methods=["GET"])
def serve_index():
    """Serve the main index file."""
    return send_from_directory(STATIC_FOLDER, "index.html")

@app.route("/<path:path>", methods=["GET"])
def serve_static_files(path):
    """Serve static files."""
    return send_from_directory(STATIC_FOLDER, path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
