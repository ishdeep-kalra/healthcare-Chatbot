import logging
import sys
from app.config import settings

def setup_logger() -> logging.Logger:
    """Configures the root logging structure for the FastAPI backend."""
    log_level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL
    }
    
    selected_level = log_level_map.get(settings.LOG_LEVEL.lower(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=selected_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger("healthcare-chatbot")
    logger.setLevel(selected_level)
    return logger

# Global logger instance
logger = setup_logger()
