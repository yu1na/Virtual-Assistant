from app.infrastructure.database.session import Base, engine, get_db, SessionLocal

# 모델 import (테이블 생성을 위해, circular import 방지)
from app.domain.user.models import User
try:
    from app.domain.report.daily.models import DailyReport
except (ImportError, RuntimeError):
    # Circular import 발생 시 무시 (나중에 필요할 때 import)
    DailyReport = None

# base.py는 Alembic용이므로 여기서는 import하지 않음
# from app.infrastructure.database.base import *
try:
    from app.domain.user.token_models import UserToken
except ImportError:
    pass

# 브레인스토밍 아이디어 모델 import
try:
    from app.domain.brainstorming.ideasave.models import BrainstormingIdea
except ImportError:
    BrainstormingIdea = None

__all__ = ["Base", "engine", "get_db", "SessionLocal"]
