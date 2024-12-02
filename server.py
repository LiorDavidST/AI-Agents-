from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import openai
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

# API Keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your_default_openai_api_key")
openai.api_key = OPENAI_API_KEY
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

# Routes
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

@app.route("/api/openai-chat", methods=["POST"])
def openai_chat():
    try:
        data = request.json
        if not data or "message" not in data:
            return jsonify({"error": "Invalid request. 'message' field is required."}), 400

        user_message = data["message"]

        # Updated call for OpenAI's API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.7
        )
        reply = response['choices'][0]['message']['content'].strip()
        return jsonify({"reply": reply})

    except openai.AuthenticationError as e:
        app.logger.error(f"OpenAI Authentication error: {str(e)}")
        return jsonify({"error": f"Authentication error: {str(e)}"}), 401
    except openai.InvalidRequestError as e:
        app.logger.error(f"OpenAI Invalid Request: {str(e)}")
        return jsonify({"error": f"Invalid request: {str(e)}"}), 400
    except openai.OpenAIError as e:
        app.logger.error(f"OpenAI API error: {str(e)}")
        return jsonify({"error": f"OpenAI API error: {str(e)}"}), 500
    except Exception as e:
        app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
