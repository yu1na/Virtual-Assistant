# Task
- Input에 주어진 파일 및 조건을 보고 코드를 수정하여 성능을 개선하는 작업을 진행해라

# Input
- 총_계산.md
- backend/councel/sourcecode/persona/ 폴더에 존재하는 파일들 중 therapy_logger.py파일을 제외한 나머지 4개의 파일
- 조건
  - rag_therapy.py
    - 병렬 API 호출
    - 조건부 Re-ranker
    - 조기 종료 조건 수정
  - persona_manager.py
    - generate_persona_with_rag → 검색 쿼리 수 문제 해결 -> 쿼리 수 줄이기
  - search_engine.py
    - multi-step: 한번만 실행
    - 조건부 Re-ranker 실행
    - 쿼리 확장 최적화
    - 감정 키워드 매칭 최적화
    - 번역 기능 제거
  - response_generator.py
    - LLM 호출 최적화
