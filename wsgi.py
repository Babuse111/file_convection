import os
import logging
import sys
from datetime import datetime
from waitress import serve
from app import app

# Configure logging with UTF-8 encoding
LOG_FILE = f'logs/server-{datetime.now().strftime("%Y%m%d")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def start_production_server():
    try:
        # Load configuration
        port = int(os.getenv('PORT', '8000'))
        threads = int(os.getenv('THREADS', '4'))
        host = os.getenv('HOST', '0.0.0.0')
        
        logger.info("Starting production server at http://%s:%s", host, port)
        logger.info("Running with %d threads", threads)
        logger.info("Logging to %s", LOG_FILE)
        
        serve(
            app,
            host=host,
            port=port,
            threads=threads,
            url_scheme='http',
            channel_timeout=300,
            cleanup_interval=30,
            asyncore_use_poll=True
        )
    except Exception as e:
        logger.error("Server failed to start: %s", str(e))
        raise

if __name__ == '__main__':
    start_production_server()