"""
모든 SQLAlchemy 모델을 import하는 파일
Alembic이 자동으로 마이그레이션을 생성할 수 있도록 함
"""

from app.infrastructure.database.session import Base

# Circular import 방지를 위해 지연 import
# Alembic이 사용할 때는 모든 모델이 이미 로드되어 있음
def _import_models():
    """모든 모델을 import (Alembic용)"""
    from app.domain.user.models import User
    from app.domain.report.daily.models import DailyReport
    return {"User": User, "DailyReport": DailyReport}

# 모듈 레벨에서도 import 시도 (circular import 발생 시 무시)
try:
    from app.domain.user.models import User
    from app.domain.report.daily.models import DailyReport
except (ImportError, RuntimeError):
    # Circular import 발생 시 None으로 설정 (Alembic이 필요할 때 다시 시도)
    User = None
    DailyReport = None

__all__ = ["Base", "User", "DailyReport", "_import_models"]
