from flask import Flask, request, jsonify, url_for
from flask_cors import CORS
import json
import os
from gtts import gTTS
import logging
import requests
from dotenv import load_dotenv

app = Flask(__name__)

# Load .env variables
load_dotenv() 

# Enable CORS for all routes 
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure static directory exists
STATIC_DIR = 'static'
AUDIO_FILE = 'audio.mp3'
AUDIO_PATH = os.path.join(STATIC_DIR, AUDIO_FILE)

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

def load_stories():
    """Load stories from city_stories.json file"""
    try:
        if os.path.exists('city_stories.json'):
            with open('city_stories.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        
        possible_paths = [
            './city_stories.json',
            os.path.join(os.path.dirname(__file__), 'city_stories.json'),
            '/opt/render/project/src/city_stories.json'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found stories file at: {path}")
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        logger.error("city_stories.json file not found in any location")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Files in current directory: {os.listdir('.')}")
        return {}
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing city_stories.json: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading stories: {e}")
        return {}

def find_story(stories, city, mood, language):
    """Find matching story based on city, mood, and language"""
    city_lower = city.lower()
    mood_lower = mood.lower()
    language_lower = language.lower()
    
    # Handle both list and dict formats
    if isinstance(stories, list):
        # If stories is a list, iterate through items
        for story_data in stories:
            if (story_data.get('city', '').lower() == city_lower and
                story_data.get('mood', '').lower() == mood_lower and
                story_data.get('language', '').lower() == language_lower):
                
                return story_data.get('story', story_data.get('text', ''))
        
        for story_data in stories:
            if (story_data.get('city', '').lower() == city_lower and
                story_data.get('mood', '').lower() == mood_lower):
                return story_data.get('story', story_data.get('text', ''))
        
        for story_data in stories:
            if story_data.get('city', '').lower() == city_lower:
                return story_data.get('story', story_data.get('text', ''))
                
    elif isinstance(stories, dict):
        for story_key, story_data in stories.items():
            if (story_data.get('city', '').lower() == city_lower and
                story_data.get('mood', '').lower() == mood_lower and
                story_data.get('language', '').lower() == language_lower):
                return story_data.get('story', story_data.get('text', ''))

        for story_key, story_data in stories.items():
            if (story_data.get('city', '').lower() == city_lower and
                story_data.get('mood', '').lower() == mood_lower):
                return story_data.get('story', story_data.get('text', ''))
        
        for story_key, story_data in stories.items():
            if story_data.get('city', '').lower() == city_lower:
                return story_data.get('story', story_data.get('text', ''))
    
    return None

def generate_story_with_groq(city, mood, language, story_length="medium"):
    """Generate story using Groq API (FREE & FAST)"""
    try:
        # Enhanced prompt for better story generation
        if story_length == "short":
            length_instruction = "Write a concise 2-paragraph story (about 150 words)"
        elif story_length == "long":
            length_instruction = "Write a detailed 4-5 paragraph story (about 400-500 words)"
        else:  # medium
            length_instruction = "Write a 3-paragraph story (about 250-300 words)"
        
        prompt = f"""You are a talented local storyteller with deep knowledge of {city}. 
        
        {length_instruction} that captures the essence of {city} for a traveler who is feeling {mood}. 
        
        Requirements:
        - Include specific local landmarks, cultural details, and authentic atmosphere
        - Match the {mood} tone throughout the story
        - Write in {language}
        - Make it immersive and emotionally engaging
        - Include sensory details (sights, sounds, smells, tastes)
        - Create a narrative that a visitor could relate to
        
        Make the story feel personal and authentic to someone experiencing {city} for the first time."""

        headers = {
            "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "llama-3.1-70b-versatile",  # Fast and high-quality model
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800 if story_length == "long" else 500,
            "temperature": 0.7  # Add creativity
        }

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return None, f"Groq API failed with status {response.status_code}"

        content = response.json()
        story_text = content["choices"][0]["message"]["content"]
        return story_text, None

    except requests.exceptions.Timeout:
        return None, "Request to Groq API timed out"
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return None, f"Network error: {str(e)}"
    except KeyError as e:
        logger.error(f"Unexpected API response format: {e}")
        return None, "Unexpected response from Groq API"
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return None, f"Failed to generate story: {str(e)}"

@app.route('/generate-story', methods=['POST'])
def generate_story():
    """Generate audio story based on city, mood, and language (from pre-written stories)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        city = data.get('city')
        mood = data.get('mood')
        language = data.get('language')
        
        if not all([city, mood, language]):
            return jsonify({
                'error': 'Missing required parameters: city, mood, language'
            }), 400
        
        # Load stories
        stories = load_stories()
        if not stories:
            return jsonify({'error': 'No stories available'}), 500
        
        # Find matching story
        story_text = find_story(stories, city, mood, language)
        
        if not story_text:
            return jsonify({
                'error': f'No story found for city: {city}, mood: {mood}, language: {language}'
            }), 404
        
        # Convert language parameter to gTTS language code
        lang_map = {
            'english': 'en',
            'spanish': 'es',
            'french': 'fr',
            'german': 'de',
            'italian': 'it',
            'portuguese': 'pt',
            'russian': 'ru',
            'japanese': 'ja',
            'korean': 'ko',
            'chinese': 'zh',
            'hindi': 'hi',
            'bengali': 'bn'
        }
        
        gtts_lang = lang_map.get(language.lower(), 'en')
        
        # Generate audio using gTTS
        try:
            tts = gTTS(text=story_text, lang=gtts_lang, slow=False)
            tts.save(AUDIO_PATH)
            logger.info(f"Audio file saved to {AUDIO_PATH}")
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            return jsonify({'error': 'Failed to generate audio'}), 500
        
        # Generate URL for the audio file
        audio_url = url_for('static', filename=AUDIO_FILE, _external=True)
        
        return jsonify({
            'success': True,
            'audio_url': audio_url,
            'story_text': story_text,
            'source': 'pre-written',
            'parameters': {
                'city': city,
                'mood': mood,
                'language': language
            }
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/generate-dynamic-story', methods=['POST'])
def generate_dynamic_story():
    """Generate dynamic story using Groq AI (FREE)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        city = data.get('city')
        mood = data.get('mood')
        language = data.get('language', 'english')
        story_length = data.get('length', 'medium')  # short, medium, long
        include_audio = data.get('include_audio', True)

        if not all([city, mood]):
            return jsonify({'error': 'Missing required fields: city, mood'}), 400

        # Check if Groq API key is available
        if not os.getenv("GROQ_API_KEY"):
            return jsonify({'error': 'Groq API key not configured'}), 500

        # Generate story using Groq
        story_text, error = generate_story_with_groq(city, mood, language, story_length)
        
        if error:
            return jsonify({'error': error}), 500

        audio_url = None
        if include_audio:
            # Convert to audio
            lang_map = {
                'english': 'en', 'hindi': 'hi', 'bengali': 'bn', 'french': 'fr',
                'german': 'de', 'spanish': 'es', 'italian': 'it', 'portuguese': 'pt',
                'russian': 'ru', 'japanese': 'ja', 'korean': 'ko', 'chinese': 'zh'
            }
            gtts_lang = lang_map.get(language.lower(), 'en')

            try:
                tts = gTTS(text=story_text, lang=gtts_lang, slow=False)
                tts.save(AUDIO_PATH)
                audio_url = url_for('static', filename=AUDIO_FILE, _external=True)
                logger.info(f"Audio generated successfully for dynamic story")
            except Exception as e:
                logger.warning(f"Failed to generate audio: {e}")
                # Continue without audio - don't fail the entire request

        return jsonify({
            'success': True,
            'story_text': story_text,
            'audio_url': audio_url,
            'source': 'groq-ai',
            'parameters': {
                'city': city,
                'mood': mood,
                'language': language,
                'length': story_length
            }
        })

    except Exception as e:
        logger.error(f"Dynamic story error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/story-options', methods=['GET'])
def get_story_options():
    """Get available cities and moods from pre-written stories"""
    try:
        stories = load_stories()
        cities = set()
        moods = set()
        languages = set()
        
        if isinstance(stories, list):
            for story in stories:
                if story.get('city'):
                    cities.add(story['city'])
                if story.get('mood'):
                    moods.add(story['mood'])
                if story.get('language'):
                    languages.add(story['language'])
        elif isinstance(stories, dict):
            for story in stories.values():
                if story.get('city'):
                    cities.add(story['city'])
                if story.get('mood'):
                    moods.add(story['mood'])
                if story.get('language'):
                    languages.add(story['language'])
        
        return jsonify({
            'cities': sorted(list(cities)),
            'moods': sorted(list(moods)),
            'languages': sorted(list(languages)),
            'supported_languages': ['english', 'hindi', 'bengali', 'french', 'german', 
                                  'spanish', 'italian', 'portuguese', 'russian', 
                                  'japanese', 'korean', 'chinese'],
            'story_lengths': ['short', 'medium', 'long']
        })
    except Exception as e:
        logger.error(f"Error getting story options: {e}")
        return jsonify({'error': 'Failed to get story options'}), 500

@app.route('/')
def root():
    """API root endpoint"""
    try:
        # Test if stories can be loaded
        stories = load_stories()
        story_count = len(stories)
        groq_configured = bool(os.getenv("GROQ_API_KEY"))
        
        return jsonify({
            'message': 'Flask Story Audio Generator API',
            'version': '2.1.0',
            'status': 'healthy',
            'stories_loaded': story_count,
            'groq_ai_enabled': groq_configured,
            'ai_provider': 'Groq (Free & Fast)',
            'endpoints': {
                'health': '/health',
                'generate_story': '/generate-story (POST) - Uses pre-written stories',
                'generate_dynamic_story': '/generate-dynamic-story (POST) - Uses Groq AI',
                'story_options': '/story-options (GET) - Get available options',
                'debug': '/debug (GET)'
            }
        })
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        return jsonify({
            'message': 'Flask Story Audio Generator API',
            'version': '2.1.0',
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to check file system"""
    try:
        debug_info = {
            'cwd': os.getcwd(),
            'files': os.listdir('.'),
            'stories_exist': os.path.exists('city_stories.json'),
            'static_exist': os.path.exists('static'),
            'groq_api_key_configured': bool(os.getenv("GROQ_API_KEY")),
            'environment_variables': list(os.environ.keys())
        }
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'groq_configured': bool(os.getenv("GROQ_API_KEY")),
        'ai_provider': 'Groq'
    })

@app.route("/ping")
def ping():
    return "pong", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)