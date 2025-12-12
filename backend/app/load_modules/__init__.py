"""
모듈 초기화 통합 관리

서버 시작 시 각 모듈의 RAG/임베딩을 초기화합니다.
각 팀원은 자기 모듈의 loader 파일만 수정하면 됩니다.

사용법 (main.py에서):
    from app.load_modules import init_all_modules
    init_all_modules()
"""

from app.load_modules.brainstorming_loader import init_brainstorming
from app.load_modules.therapy_loader import init_therapy
from app.load_modules.insurance_rag_loader import init_insurance_rag
from app.load_modules.report_loader import init_reports
from app.load_modules.hr_rag_loader import init_hr_rag


def init_all_modules():
    """
    모든 모듈 초기화 실행
    
    새 모듈 추가 시 여기에 호출 추가하세요.
    """
    print("=" * 50)
    print("📦 [load_modules] RAG 임베딩 초기화 시작")
    print("=" * 50)
    
    # 브레인스토밍 모듈
    print("\n[1] 브레인스토밍 모듈 체크 중...")
    init_brainstorming()
    
    # 심리 상담 모듈
    init_therapy()
    
    # Insurance RAG 모듈
    print("\n[2] Insurance RAG 모듈 체크 중...")
    init_insurance_rag()
    
    # 보고서 모듈
    print("\n[3] 보고서 모듈 체크 중...")
    init_reports()
    
    # HR RAG 모듈
    print("\n[4] HR RAG 모듈 체크 중...")
    init_hr_rag()
    
    # TODO: 다른 팀원 모듈 추가 시 아래 형식으로
    # print("\n[X] OOO 모듈 체크 중...")
    # from app.load_modules.xxx_loader import init_xxx
    # init_xxx()
    
    print("\n" + "=" * 50)
    print("✅ [load_modules] RAG 임베딩 초기화 완료")
    print("=" * 50)
