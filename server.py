from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import cohere
from datetime import datetime, timedelta
import os
import jwt

app = Flask(__name__)

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": ["https://ai-agents-1yi8.onrender.com"]}})

# Configuration
UPLOAD_FOLDER = "uploads"
LAWS_FOLDER = "HookeyMecher"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
                with open(os.path.join(LAWS_FOLDER, filename), "r", encoding="utf-8") as f:
                    law_id = filename.replace(".txt", "")
                    laws[law_id] = f.read()
    except Exception as e:
        app.logger.error(f"Error loading laws: {str(e)}")
    return laws

@app.route("/api/contract-compliance", methods=["POST"])
def contract_compliance():
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
    selected_laws = request.form.getlist("selected_laws")
    if not file.filename or not selected_laws:
        return jsonify({"error": "File and selected laws must be provided"}), 400

    # Save uploaded file
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    # Read uploaded file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            user_content = f.read()
    except Exception as e:
        return jsonify({"error": f"Failed to read the uploaded file: {str(e)}"}), 500

    # Load laws
    laws = load_laws()
    compliance_results = []

    # Compare uploaded file with selected laws
    for law_id in selected_laws:
        if law_id in laws:
            law_text = laws[law_id]
            try:
                # Use Cohere to compare the user's contract with the law
                response = co.classify(
                    inputs=[user_content],
                    examples=[
                        {"text": law_text, "label": "Compliant"}
                    ]
                )
                similarity = response.classifications[0].confidence
                compliance_results.append({
                    "law_id": law_id,
                    "law_name": laws[law_id],
                    "similarity": similarity,
                    "status": "Compliant" if similarity > 0.8 else "Non-Compliant"
                })
            except Exception as e:
                compliance_results.append({
                    "law_id": law_id,
                    "status": "Error",
                    "error": f"Failed to compare with law: {str(e)}"
                })
        else:
            compliance_results.append({
                "law_id": law_id,
                "status": "Not Found",
                "error": "The selected law is not available in the system."
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
        app.logger.error(f"File not found: {path} - {str(e)}")
        return make_response(f"File not found: {path}", 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
