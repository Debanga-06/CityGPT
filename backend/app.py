import os
import json
import random
import logging
from flask import Flask, request, jsonify, send_file, url_for
from flask_cors import CORS
from gtts import gTTS
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
AUDIO_FILE = "audio.mp3"
AUDIO_PATH = os.path.join("static", AUDIO_FILE)
STORIES_FILE = "city_stories.json"

# Flask setup
app = Flask(__name__)
CORS(app)

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    return jsonify({"status": "Server is running"}), 200

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/ping')
def ping():
    return jsonify({"message": "pong"}), 200

@app.route('/debug', methods=['GET'])
def debug():
    return jsonify({
        "cwd": os.getcwd(),
        "env": dict(os.environ),
        "files": os.listdir('.')
    })

@app.route('/generate-story', methods=['POST'])
def generate_story():
    try:
        data = request.get_json()
        city = data.get('city')
        mood = data.get('mood')
        language = data.get('language', 'english')

        logger.info(f"Input: city={city}, mood={mood}, language={language}")

        with open(STORIES_FILE, "r", encoding="utf-8") as f:
            city_data = json.load(f)

        if city not in city_data or mood not in city_data[city]:
            return jsonify({'error': 'No story available for given city and mood'}), 404

        story_text = random.choice(city_data[city][mood])

        # Convert language for gTTS
        lang_map = {
            'english': 'en', 'hindi': 'hi', 'bengali': 'bn', 'french': 'fr',
            'german': 'de', 'spanish': 'es'
        }
        gtts_lang = lang_map.get(language.lower(), 'en')

        try:
            tts = gTTS(text=story_text, lang=gtts_lang)
            tts.save(AUDIO_PATH)
            audio_url = url_for('static', filename=AUDIO_FILE, _external=True)
        except Exception as e:
            audio_url = None
            logger.warning(f"gTTS failed: {e}")

        return jsonify({
            'success': True,
            'story_text': story_text,
            'audio_url': audio_url,
            'parameters': {
                'city': city,
                'mood': mood,
                'language': language
            }
        })

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/generate-dynamic-story', methods=['POST'])
def generate_dynamic_story():
    try:
        data = request.get_json()
        city = data.get('city')
        mood = data.get('mood')
        language = data.get('language', 'english')

        if not all([city, mood, language]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Claude prompt
        prompt = (
            f"You are a local storyteller. Create a 3-paragraph immersive, emotional story "
            f"for a traveler visiting {city} in a {mood} mood. Use rich cultural details and local charm."
        )

        headers = {
            "x-api-key": os.getenv("CLAUDE_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 700,
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)

        if response.status_code != 200:
            return jsonify({'error': 'Claude API failed', 'details': response.text}), 500

        content = response.json()
        story_text = content["content"][0]["text"]

        # Language conversion for gTTS
        lang_map = {
            'english': 'en', 'hindi': 'hi', 'bengali': 'bn', 'french': 'fr',
            'german': 'de', 'spanish': 'es'
        }
        gtts_lang = lang_map.get(language.lower(), 'en')

        try:
            tts = gTTS(text=story_text, lang=gtts_lang)
            tts.save(AUDIO_PATH)
            audio_url = url_for('static', filename=AUDIO_FILE, _external=True)
        except Exception as e:
            audio_url = None
            logger.warning(f"Failed to generate audio: {e}")

        return jsonify({
            'success': True,
            'story_text': story_text,
            'audio_url': audio_url,
            'parameters': {
                'city': city,
                'mood': mood,
                'language': language
            }
        })

    except Exception as e:
        logger.error(f"Dynamic story error: {e}")
        return jsonify({'error': 'Server error'}), 500

if __name__ == '__main__':
    app.run(debug=True)