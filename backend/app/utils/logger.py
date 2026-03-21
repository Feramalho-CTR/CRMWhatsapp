import logging
import sys
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    """Confingura e retorna o logger global da aplicação com saída para console e arquivo rotativo."""
    logger = logging.getLogger("crm_whatsapp")
    
    # Se já tiver handlers (ex: hot reload), não adiciona duplicados
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    # Formatter estruturado com tempo, nível, módulo e mensagem
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler: 5MB max por arquivo, guarda até 3 backups
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'app.log')
    
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Instância global para ser importada (`from app.utils.logger import logger`)
logger = setup_logger()
