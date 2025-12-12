"""
브레인스토밍 아이디어 테이블 생성 스크립트

사용법:
    python -m app.domain.brainstorming.ideasave.migrate
"""
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.database.session import engine, Base
from app.domain.brainstorming.ideasave.models import BrainstormingIdea
from app.domain.user.models import User  # FK 참조를 위해 필요


def create_table():
    """brainstorming_ideas 테이블 생성"""
    
    print("=" * 60)
    print("🚀 브레인스토밍 아이디어 테이블 생성 시작...")
    print("=" * 60)
    
    try:
        # 테이블 생성 (이미 존재하면 무시됨)
        Base.metadata.create_all(bind=engine, tables=[BrainstormingIdea.__table__])
        
        print("\n✅ 테이블 생성 완료!")
        print("\n📋 생성된 테이블:")
        print(f"   - {BrainstormingIdea.__tablename__}")
        print("\n📊 테이블 구조:")
        print(f"   - id: INTEGER (PK)")
        print(f"   - user_id: INTEGER (FK -> users.id)")
        print(f"   - title: VARCHAR(255)")
        print(f"   - description: TEXT")
        print(f"   - created_at: TIMESTAMP")
        
        print("\n" + "=" * 60)
        print("🎉 마이그레이션 성공!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("\n💡 해결 방법:")
        print("   1. DB가 실행 중인지 확인")
        print("   2. .env 파일의 DATABASE_URL 확인")
        print("   3. users 테이블이 먼저 생성되어 있는지 확인")
        sys.exit(1)


def check_table():
    """테이블 생성 확인"""
    from sqlalchemy import inspect
    
    print("\n🔍 테이블 확인 중...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if BrainstormingIdea.__tablename__ in tables:
        print(f"✅ '{BrainstormingIdea.__tablename__}' 테이블 존재!")
        
        # 컬럼 정보 출력
        columns = inspector.get_columns(BrainstormingIdea.__tablename__)
        print("\n📋 컬럼 목록:")
        for col in columns:
            print(f"   - {col['name']}: {col['type']}")
    else:
        print(f"❌ '{BrainstormingIdea.__tablename__}' 테이블 없음!")


if __name__ == "__main__":
    create_table()
    check_table()
