from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
import cohere
from datetime import datetime
import pytz
import requests
import os

app = Flask(__name__)

# Enable CORS with stricter policy
CORS(app, resources={r"/api/*": {"origins": ["https://ai-agents-1yi8.onrender.com"]}})

# Set a maximum upload size (e.g., 5MB)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['ai_service']
users_collection = db['users']

# API Keys
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "your_default_cohere_api_key")
co = cohere.Client(COHERE_API_KEY)
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "your_default_weather_api_key")

# Helper functions
def get_weather(city="London"):
    try:
        url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            temp = data["current"]["temp_c"]
            description = data["current"]["condition"]["text"]
            return f"The current weather in {city} is {temp}°C with {description}."
        else:
            return "Unable to fetch weather data at the moment. Please try again later."
    except Exception as e:
        app.logger.error(f"Weather API error: {str(e)}")
        return f"Error fetching weather: {str(e)}"

def get_user_location(ip_address=""):
    try:
        url = f"https://ipinfo.io/{ip_address}?token=YOUR_IPINFO_API_KEY"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            city = data.get("city", None)
            country = data.get("country", None)
            timezone = data.get("timezone", None)
            return city, country, timezone
        return None, None, None
    except Exception as e:
        app.logger.error(f"IP Info API error: {str(e)}")
        return None, None, None

def get_current_time(city=None, timezone=None):
    try:
        tz = pytz.timezone(timezone) if timezone else pytz.timezone("UTC")
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        app.logger.error(f"Time error: {str(e)}")
        return f"Error fetching time: {str(e)}"

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

    # Check if the email is already registered
    if users_collection.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 400

    # Hash the password and save the user
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

    # Find user by email
    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # Verify the password
    if check_password_hash(user["password_hash"], password):
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"error": "Invalid email or password"}), 401

# Cohere Chat Endpoint
@app.route("/api/cohere-chat", methods=["POST"])
def cohere_chat():
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
