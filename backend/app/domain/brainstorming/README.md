# 🧠 브레인스토밍 RAG 시스템

브레인스토밍 기법을 ChromaDB + RAG로 검색하는 시스템입니다.

## 📁 구조

```
brainstorming/                           # ✅ 모듈 독립성
├── data/
│   ├── prompts/
│   │   └── ChunkBrainstormingTechniques.md  # 원본 청크 파일
│   ├── embeddings/
│   │   ├── parsed_chunks.json               # 파싱된 청크
│   │   └── embedded_chunks.json             # 임베딩된 청크 (2.3MB)
│   ├── chroma/                              # ✅ 모듈 전용 벡터 DB
│   │   ├── brainstorming_techniques/        # 영구 RAG (SCAMPER, Mind Mapping 등)
│   │   └── ephemeral_session_*/             # 임시 RAG (세션별 자동 생성/삭제)
│   └── ephemeral/                           # 세션별 임시 데이터 폴더
│       └── {session_id}/                    # 각 세션의 UUID 폴더
│
├── parser.py                # 1단계: MD → JSON 파싱
├── embedder_standalone.py   # 2단계: JSON → 임베딩 추가
├── chroma_loader.py         # 3단계: ChromaDB에 로드
├── service.py               # 4단계: RAG 검색 서비스
├── test_search.py           # 🎮 테스트 스크립트 (메뉴 방식)
├── bsmanual.py              # 📚 RAG 테스트용 매뉴얼 (대화형)
│
├── session_manager.py       # 🆕 세션 관리 (동시성 처리)
├── ephemeral_rag.py         # 🆕 임시 RAG (세션별 임베딩)
├── domain_hints.py          # 🆕 직군별 힌트 Add-on (선택적)
└── idea_generator.py        # 🆕 아이디어 생성 도구 (전체 플로우)
```

### ✅ 다른 팀원과 충돌 방지

- **모든 데이터를 모듈 내부에 저장**: `brainstorming/data/` 폴더 안에만 저장
- **독립적인 ChromaDB**: `brainstorming/data/chroma/` 전용 경로 사용
- **다른 모듈과 완전히 분리**: 각 팀원이 자신의 모듈 폴더에서만 작업

## 🚀 실행 방법

### 1️⃣ 데이터 준비 (이미 완료됨 ✅)

```bash
# 1단계: 파싱
cd /Users/jinmokim/dev/Virtual-Assistant/backend
python3 -m app.domain.brainstorming.parser

# 2단계: 임베딩
python3 app/domain/brainstorming/embedder_standalone.py

# 3단계: ChromaDB 로드
python3 app/domain/brainstorming/chroma_loader.py
```

### 2️⃣ RAG 테스트 🎮

**방법 1: 매뉴얼 (대화형, 추천!)**
```bash
cd /Users/jinmokim/dev/Virtual-Assistant/backend/app/domain/brainstorming
python bsmanual.py
```

**방법 2: 테스트 스크립트 (메뉴 방식)**
```bash
python test_search.py
```

### 3️⃣ 아이디어 생성 도구 🎨 (NEW!)

**전체 플로우 자동 실행:**
```bash
cd /Users/jinmokim/dev/Virtual-Assistant/backend/app/domain/brainstorming
python3 idea_generator.py
```

**플로우:**
1. **Q1**: 목적/도메인 입력 ("어디에 쓸 아이디어가 필요하신가요?")
2. **Q2**: LLM 워밍업 질문 생성 (2-3개) → "네" 입력 대기
3. **Q3**: 20초 자유연상 입력 (최소 10개)
4. **아이디어 생성**: Q1 목적 + Q3 키워드 + 영구 RAG 기법 결합
5. **SWOT 분석**: 각 아이디어별 강점/약점/기회/위협 분석
6. **삭제 확인**: "네" 입력 시 모든 임시 데이터 삭제 (데이터 오염 방지)

**동시성 처리:**
- UUID 기반 세션 관리 (여러 사용자 동시 사용 가능)
- `threading.Lock`으로 세션 딕셔너리 보호 (자바의 ConcurrentHashMap과 유사)
- 세션별 독립적인 ChromaDB 컬렉션 (`ephemeral_session_{uuid}`)
- 세션 종료 시 임시 데이터 완전 삭제 (아이디어 유출 방지)

**Add-on 힌트 모듈** (선택적):
- 직군별 방향성 제시 (수험생, 직장인, 크리에이터, 소상공인, 기획자, 개발자, 작가)
- Q1 목적 분석으로 자동 감지
- **힌트는 저장 안 함**: 일회성 프롬프트 조합용 (Ephemeral RAG 철학 유지)
- 편향 최소화: 강하게 유도하지 않고 가볍게 방향성만 제시
- 독립 모듈: `domain_hints.py` 수정·삭제 자유

## 💻 테스트 모드

### 메뉴 선택

```
1. 기본 검색 테스트 - 미리 정의된 쿼리로 검색
2. RAG AI 제안 테스트 - GPT가 상황에 맞는 제안 생성
3. 대화형 모드 - 자유롭게 검색하기
4. 전체 테스트 - 1 + 2 + 3 순서로 실행
0. 종료
```

### 대화형 모드 명령어

```bash
# 1. 기본 검색
팀 협업 방법

# 2. RAG AI 제안 (GPT 사용)
rag 신제품 아이디어를 빠르게 내고 싶어요

# 3. 전체 목록 보기
list

# 4. 특정 기법 상세 보기
id 01

# 5. 종료
quit
```

## 📊 검색 예시

### 1. 기본 검색

```bash
🔍 입력 >>> 팀 협업을 위한 브레인스토밍

📋 5개의 결과를 찾았습니다:
------------------------------------------------------------

1. [조용한 브레인스토밍 기법] (유사도: 58.52%)
   청크 ID: 25
   글자 수: 528
   
2. [브레인스토밍 기초: 브레인스토밍 방법] (유사도: 57.18%)
   청크 ID: 17
   글자 수: 512
```

### 2. RAG AI 제안

```bash
🔍 입력 >>> rag 5명 팀으로 신제품 아이디어 회의를 1시간 동안 해야 해요

💡 AI 제안:
이 상황에 가장 적합한 브레인스토밍 기법을 추천드립니다:

1. **마인드 매핑** (추천도: 높음)
   - 5명 팀에 적합하며 1시간 안에 실행 가능
   - 신제품의 다양한 측면을 체계적으로 탐색
   - 실행방법: 화이트보드 중앙에 "신제품" 적고...

2. **스타버스팅** (추천도: 중간)
   - 누가, 무엇을, 언제, 어디서, 왜, 어떻게 질문
   - 제품의 모든 요소를 꼼꼼히 검토

📚 참고한 자료 (3개):
   1. 마인드 매핑 (유사도: 62.3%)
   2. 스타버스팅 (유사도: 59.1%)
   3. SWOT 분석 (유사도: 55.8%)
```

## 🔧 기술 스택

- **파싱**: Python + 정규식
- **임베딩**: OpenAI text-embedding-3-large (3072 차원)
- **벡터 DB**: ChromaDB (코사인 유사도)
- **RAG**: OpenAI GPT-4o
- **저장**: 
  - JSON (텍스트 + 임베딩)
  - ChromaDB (벡터 검색용)

## 📈 성능

- **청크 수**: 39개
- **임베딩 비용**: ~$0.000016 (약 0.02원)
- **검색 속도**: < 1초
- **유사도 정확도**: 평균 60%+

## 🎯 다음 단계

현재는 콘솔 테스트만 가능합니다. 다음 작업:

1. ✅ FastAPI 엔드포인트 추가 (`schemas.py`, API 라우터)
2. ✅ 프론트엔드 연결
3. ✅ 사용자 히스토리 저장 (DB)
4. ✅ 즐겨찾기 기능

## 💡 팁

- `list` 명령어로 전체 기법 목록을 먼저 확인해보세요
- RAG 제안은 OpenAI API를 호출하므로 약간의 비용이 발생합니다
- 검색어는 자연어로 입력하면 됩니다 (예: "빠른 아이디어 도출")

