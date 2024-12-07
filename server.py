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

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": ["https://ai-agents-1yi8.onrender.com"]}})

# Configurations
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['ai_service']
users_collection = db['users']

COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "your_default_cohere_api_key")
JWT_SECRET = os.environ.get("JWT_SECRET", "JWT_secret_key")
JWT_EXPIRATION_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", 30))
co = cohere.Client(COHERE_API_KEY)

LAW_URLS = {
    "1": "https://www.nevo.co.il/law_html/law00/72490.htm",  # Sales Law 1973
    "2": "https://www.nevo.co.il/law_html/law00/70330.htm",  # Investment Assurance 1974
}

# Helper functions
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

def fetch_law_content(law_urls):
    """Fetch the content of laws from URLs."""
    law_contents = {}
    for law_id, url in law_urls.items():
        try:
            response = requests.get(url)
            response.raise_for_status()
            law_contents[law_id] = response.text
        except Exception as e:
            law_contents[law_id] = f"Error fetching law content: {str(e)}"
    return law_contents

@app.route("/api/contract-compliance", methods=["POST"])
def contract_compliance():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token is missing"}), 401

    token = token.replace("Bearer ", "")
    email = decode_token(token)
    if not email:
        return jsonify({"error": "Invalid or expired token"}), 401

    if "file" not in request.files or not request.form.get("selected_laws"):
        return jsonify({"error": "File and selected laws are required"}), 400

    file = request.files["file"]
    selected_laws = request.form.getlist("selected_laws")
    if not file.filename or not selected_laws:
        return jsonify({"error": "File and selected laws must be provided"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    # Read uploaded file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            user_content = f.read()
    except Exception as e:
        return jsonify({"error": f"Failed to read the uploaded file: {str(e)}"}), 500

    # Fetch law contents
    selected_law_urls = {key: LAW_URLS[key] for key in selected_laws if key in LAW_URLS}
    law_contents = fetch_law_content(selected_law_urls)

    # Compare file content with laws
    compliance_results = []
    for law_id, law_text in law_contents.items():
        if isinstance(law_text, str) and law_text.startswith("Error"):
            compliance_results.append({"law_id": law_id, "status": "Error", "details": law_text})
        else:
            compliance_results.append({
                "law_id": law_id,
                "status": "Compliant" if user_content in law_text else "Non-Compliant",
                "details": f"Checked against {LAW_URLS[law_id]}",
            })

    return jsonify({"result": compliance_results}), 200

# Static File Serving
@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>", methods=["GET"])
def serve_static_files(path):
    try:
        return send_from_directory(".", path)
    except Exception as e:
        return make_response(f"File not found: {path}", 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
