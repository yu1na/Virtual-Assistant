"""
RAG 시스템 유틸리티

공통으로 사용되는 로깅 설정 등을 관리합니다.
"""

import logging
from app.core.config import settings


def get_logger(name: str) -> logging.Logger:
    """
    RAG 시스템용 로거 생성
    
    기존 core/config.py의 LOG_LEVEL 설정을 재사용합니다.
    
    Args:
        name: 로거 이름
        
    Returns:
        logging.Logger: 설정된 로거
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # 핸들러가 없을 때만 설정
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    return logger

