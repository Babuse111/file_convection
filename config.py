import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secure-secret-key')
    UPLOAD_FOLDER = os.getenv('UPLOADS_FOLDER', 'uploads')
    OUTPUT_FOLDER = os.getenv('OUTPUTS_FOLDER', 'outputs')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size