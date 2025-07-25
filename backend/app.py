from flask import Flask, request, jsonify, url_for
from flask_cors import CORS
import json
import os
from gtts import gTTS
import logging

app = Flask(__name__)

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

@app.route('/generate-story', methods=['POST'])
def generate_story():
    """Generate audio story based on city, mood, and language"""
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
            'chinese': 'zh'
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
            'parameters': {
                'city': city,
                'mood': mood,
                'language': language
            }
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/')
def root():
    """API root endpoint"""
    try:
        # Test if stories can be loaded
        stories = load_stories()
        story_count = len(stories)
        
        return jsonify({
            'message': 'Flask Story Audio Generator API',
            'version': '1.0.0',
            'status': 'healthy',
            'stories_loaded': story_count,
            'endpoints': {
                'health': '/health',
                'generate_story': '/generate-story (POST)'
            }
        })
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        return jsonify({
            'message': 'Flask Story Audio Generator API',
            'version': '1.0.0',
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to check file system"""
    try:
        import os
        debug_info = {
            'cwd': os.getcwd(),
            'files': os.listdir('.'),
            'python_path': os.sys.path,
            'stories_exist': os.path.exists('city_stories.json'),
            'static_exist': os.path.exists('static')
        }
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

@app.route("/ping")
def ping():
    return "pong", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
