# 자동 저장 프로세스 알고리즘 흐름도
# 백엔드 서버 시작 시 실행되는 프로세스 흐름도(청크 파일 생성 -> 임베딩 파일 생성 -> Vector DB 저장)

## 전체 프로세스 개요
# 청크 파일 생성(create_chunk_files.py) -> 217줄 이하 참고
# 임베딩 파일 생성(create_openai_embeddings.py) -> 386줄 이하 참고
# Vector DB 저장(save_to_vectordb.py) -> 512줄 이하 참고
# 전체적인 흐름만 확인할 경우에는 74줄 이하 참고

```
┌─────────────────────────────────────────────────────────────┐
│                    automatic_save.py                         │
│              (통합 프로세스 관리자)                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   AutomaticSaveManager.run()           │
        └───────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Step 1:      │  │ Step 2:       │  │ Step 3:       │
│ 청크 생성     │  │ 임베딩 생성    │  │ Vector DB 저장│
└───────────────┘  └───────────────┘  └───────────────┘
```

### 실행 흐름도

```
시작
 │
 ▼
┌─────────────────────────────┐
│  AutomaticSaveManager.run() │
└─────────────────────────────┘
 │
 ├─→ Step 1: 청크 파일 생성
 │    │
 │    ├─→ 폴더/파일 존재 확인
 │    │
 │    ├─→ [존재] → 건너뛰기
 │    │
 │    └─→ [없음] → run_script(create_chunk_files.py)
 │         │
 │         └─→ subprocess.run() 실행
 │
 ├─→ Step 2: 임베딩 파일 생성
 │    │
 │    ├─→ 폴더/파일 존재 확인
 │    │
 │    ├─→ [존재] → 건너뛰기
 │    │
 │    └─→ [없음] → run_script(create_openai_embeddings.py)
 │         │
 │         └─→ subprocess.run() 실행
 │
 └─→ Step 3: Vector DB 저장
      │
      ├─→ 컬렉션 존재 확인
      │
      ├─→ [존재] → 건너뛰기
      │
      └─→ [없음] → run_script(save_to_vectordb.py)
           │
           └─→ subprocess.run() 실행
 │
 ▼
성공/실패
```

## 전체 프로세스 통합 흐름도

```
┌─────────────────────────────────────────────────────────────┐
│                    automatic_save.py                         │
│              AutomaticSaveManager.run()                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   Step 1: 청크 파일 생성               │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   create_chunk_files.py                │
        │   - PDF 텍스트 추출                    │
        │   - 텍스트 정제화                      │
        │   - 섹션 분할                          │
        │   - 토큰 제한 분할                      │
        │   - Overlap 추가                       │
        │   - JSON 저장                          │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   Step 2: 임베딩 파일 생성             │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   create_openai_embeddings.py          │
        │   - 청크 파일 로드                     │
        │   - OpenAI API 호출                   │
        │   - 임베딩 생성                        │
        │   - JSON 저장                          │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   Step 3: Vector DB 저장              │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   save_to_vectordb.py                 │
        │   - 임베딩 파일 로드                   │
        │   - ChromaDB 연결                      │
        │   - 컬렉션 생성/가져오기               │
        │   - 배치 저장                          │
        │   - 검증                               │
        └───────────────────────────────────────┘
                            │
                            ▼
                        완료
```

---

## 데이터 흐름

```
PDF 파일
  │
  ▼
[create_chunk_files.py]
  │
  ├─→ 텍스트 추출
  ├─→ 정제화
  ├─→ 섹션 분할
  ├─→ 토큰 분할
  └─→ Overlap 추가
  │
  ▼
청크 JSON 파일
  (*_chunks.json)
  │
  ▼
[create_openai_embeddings.py]
  │
  ├─→ 청크 로드
  ├─→ OpenAI API 호출
  └─→ 임베딩 생성
  │
  ▼
임베딩 JSON 파일
  (*_embeddings.json)
  │
  ▼
[save_to_vectordb.py]
  │
  ├─→ 임베딩 로드
  ├─→ ChromaDB 저장
  └─→ 검증
  │
  ▼
ChromaDB Vector Store
  (vector_adler 컬렉션)
```

---

## 1. automatic_save.py - 통합 프로세스 관리자

### 주요 클래스 및 메서드

```
AutomaticSaveManager
│
├── __init__()
│   ├── 경로 설정 (dataset, chunkfiles, embeddings, vector_db)
│   └── 스크립트 경로 설정
│
├── check_folder_and_files()
│   └── 폴더 및 파일 존재 여부 확인
│
├── create_folder_if_not_exists()
│   └── 폴더 생성 (없을 경우)
│
├── run_script()
│   └── subprocess.run()으로 Python 스크립트 실행
│
├── step1_create_chunks()
│   ├── 청크 파일 존재 확인
│   ├── 없으면 → create_chunk_files.py 실행
│   └── 있으면 → 건너뛰기
│
├── step2_create_embeddings()
│   ├── 임베딩 파일 존재 확인
│   ├── 없으면 → create_openai_embeddings.py 실행
│   └── 있으면 → 건너뛰기
│
├── step3_save_to_vectordb()
│   ├── Vector DB 컬렉션 존재 확인
│   ├── 없으면 → save_to_vectordb.py 실행
│   └── 있으면 → 건너뛰기
│
└── run()
    ├── step1_create_chunks() 실행
    ├── step2_create_embeddings() 실행
    ├── step3_save_to_vectordb() 실행
    └── 실패 시 rollback() 호출
```

---

## 2. create_chunk_files.py - 청크 파일 생성

### 주요 클래스 및 메서드

```
ChunkCreator
│
├── __init__(max_tokens=500, overlap_ratio=0.2)
│   └── 토큰 인코딩 모델 초기화
│
├── count_tokens()
│   └── 텍스트의 토큰 수 계산
│
├── extract_text_from_pdf()
│   ├── PyMuPDF로 PDF 텍스트 추출
│   └── 하이픈으로 끝나는 단어 복원
│
├── clean_pdf_text()
│   ├── 페이지 번호 제거
│   ├── 표/그래프 특수문자 제거
│   ├── 참고문헌 섹션 제거
│   ├── URL/이메일 제거
│   ├── 한글 제거
│   ├── 반복 특수문자 제거
│   └── 공백 정리
│
├── extract_metadata_adler()
│   └── 파일명에서 메타데이터 추출
│
├── split_by_sections()
│   ├── 마크다운 섹션 분할 (#, ## 기준)
│   └── (섹션 제목, 섹션 내용) 튜플 리스트 반환
│
├── add_overlap()
│   ├── 이전 청크의 마지막 20% 가져오기
│   └── 현재 청크 앞에 추가
│
├── split_large_section()
│   ├── 토큰 수 확인
│   ├── [토큰 ≤ max_tokens] → 그대로 반환
│   └── [토큰 > max_tokens] → 문단 단위로 분할
│
├── process_file()
│   ├── PDF/MD 파일 처리
│   ├── 섹션별 분할
│   ├── 큰 섹션 분할
│   └── Overlap 적용
│
├── create_chunk_objects()
│   └── 청크 객체 생성 (id, text, metadata)
│
├── process_single_file()
│   ├── 메타데이터 추출
│   ├── 파일 청크 분할
│   ├── 청크 객체 생성
│   └── JSON 파일로 저장
│
└── process_directory()
    ├── [save_individually=True] → 개별 파일로 저장
    └── [save_individually=False] → 단일 파일로 저장
```

### 실행 흐름도

```
main() 시작
 │
 ▼
┌─────────────────────────────┐
│ 경로 설정 및 ChunkCreator    │
│ 초기화 (max_tokens=500)     │
└─────────────────────────────┘
 │
 ▼
┌─────────────────────────────┐
│ 카테고리별 반복 처리         │
│ (case, theory, interventions,│
│  qna, tone)                 │
└─────────────────────────────┘
 │
 ├─→ 각 카테고리 디렉토리
 │    │
 │    ├─→ PDF 파일 목록 가져오기
 │    │
 │    └─→ 각 PDF 파일 처리
 │         │
 │         ├─→ extract_text_from_pdf()
 │         │    └─→ PDF 텍스트 추출
 │         │
 │         ├─→ clean_pdf_text()
 │         │    └─→ 텍스트 정제화
 │         │
 │         ├─→ split_by_sections()
 │         │    └─→ 섹션별 분할
 │         │
 │         ├─→ split_large_section()
 │         │    └─→ 토큰 제한에 맞춰 분할
 │         │
 │         ├─→ add_overlap()
 │         │    └─→ Overlap 추가 (20%)
 │         │
 │         ├─→ create_chunk_objects()
 │         │    └─→ 청크 객체 생성
 │         │
 │         └─→ JSON 파일로 저장
 │              (파일명_chunks.json)
 │
 ▼
통계 출력 및 완료
```

### 상세 처리 흐름

```
PDF 파일 입력
 │
 ▼
┌─────────────────────┐
│ extract_text_from_pdf│
│ - 페이지별 텍스트 추출│
│ - 하이픈 단어 복원   │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ clean_pdf_text()     │
│ - 페이지 번호 제거   │
│ - 특수문자 제거      │
│ - 참고문헌 제거      │
│ - URL/이메일 제거    │
│ - 한글 제거          │
│ - 공백 정리          │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ split_by_sections()  │
│ - # 제목 기준 분할   │
│ - ## 섹션 기준 분할  │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ split_large_section()│
│ - 토큰 수 확인       │
│ - 문단 단위 분할     │
│ - 줄 단위 분할       │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ add_overlap()        │
│ - 이전 청크 20% 추가 │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ create_chunk_objects()│
│ - ID 생성            │
│ - 메타데이터 추가    │
└─────────────────────┘
 │
 ▼
JSON 파일 저장
```

---

## 3. create_openai_embeddings.py - OpenAI 임베딩 생성

### 주요 함수

```
main()
│
├── API 키 확인
│
├── 청크 파일 목록 가져오기
│   └── *_chunks.json 파일 검색
│
└── 각 청크 파일 처리
    │
    ├─→ load_chunks()
    │    └─→ JSON 파일 로드
    │
    ├─→ create_embeddings()
    │    ├── OpenAI 클라이언트 초기화
    │    ├── 배치 단위로 처리 (BATCH_SIZE=100)
    │    ├── OpenAI API 호출
    │    └── 임베딩 벡터 추출
    │
    ├─→ save_embeddings()
    │    ├── 청크 + 임베딩 결합
    │    └── JSON 파일로 저장
    │
    └─→ 결과 출력
```

### 실행 흐름도

```
main() 시작
 │
 ▼
┌─────────────────────────────┐
│ API 키 확인                  │
│ (OPENAI_API_KEY)            │
└─────────────────────────────┘
 │
 ▼
┌─────────────────────────────┐
│ 청크 파일 목록 가져오기      │
│ (chunkfiles/*_chunks.json)   │
└─────────────────────────────┘
 │
 ▼
┌─────────────────────────────┐
│ 각 청크 파일 반복 처리       │
└─────────────────────────────┘
 │
 ├─→ load_chunks()
 │    └─→ JSON 파일 로드
 │
 ├─→ create_embeddings()
 │    │
 │    ├─→ OpenAI 클라이언트 초기화
 │    │
 │    ├─→ 배치 단위로 처리
 │    │    │
 │    │    ├─→ 텍스트 추출
 │    │    │
 │    │    ├─→ OpenAI API 호출
 │    │    │    └─→ embeddings.create()
 │    │    │
 │    │    └─→ 임베딩 벡터 추출
 │    │
 │    └─→ 모든 배치 처리 완료
 │
 ├─→ save_embeddings()
 │    │
 │    ├─→ 청크 + 임베딩 결합
 │    │
 │    └─→ JSON 파일로 저장
 │         (파일명_embeddings.json)
 │
 ▼
통계 출력 및 완료
```

### 임베딩 생성 상세 흐름

```
청크 데이터
 │
 ▼
┌─────────────────────┐
│ 텍스트 추출          │
│ (chunk['text'])     │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ 배치 분할            │
│ (BATCH_SIZE=100)    │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ OpenAI API 호출      │
│ - model:            │
│   text-embedding-   │
│   3-large           │
│ - input: batch_texts│
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ 임베딩 벡터 추출     │
│ (response.data)     │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ 청크 + 임베딩 결합   │
│ chunk['embedding']  │
└─────────────────────┘
 │
 ▼
JSON 파일 저장
```

---

## 4. save_to_vectordb.py - Vector DB 저장

### 주요 클래스 및 메서드

```
VectorDBManager
│
├── __init__(db_path)
│   └── ChromaDB 클라이언트 초기화
│
├── _initialize_client()
│   ├── DB 폴더 생성
│   └── PersistentClient 생성
│
├── load_embedding_file()
│   └── JSON 파일 로드
│
├── create_or_get_collection()
│   ├── 기존 컬렉션 확인
│   ├── [존재] → 기존 컬렉션 반환
│   └── [없음] → 새 컬렉션 생성
│
├── save_to_collection()
│   ├── 기존 ID 확인 (중복 방지)
│   ├── 데이터 준비 (ids, embeddings, documents, metadatas)
│   ├── 배치 단위로 저장 (batch_size=1000)
│   └── 저장 결과 반환
│
└── verify_collection()
    ├── 컬렉션 정보 조회
    └── 샘플 데이터 확인
```

### 실행 흐름도

```
main() 시작
 │
 ▼
┌─────────────────────────────┐
│ 경로 설정                    │
│ (embeddings, vector_db)      │
└─────────────────────────────┘
 │
 ▼
┌─────────────────────────────┐
│ 임베딩 파일 목록 가져오기     │
│ (*_embeddings.json)          │
└─────────────────────────────┘
 │
 ▼
┌─────────────────────────────┐
│ VectorDBManager 초기화       │
│ - ChromaDB 클라이언트 생성   │
└─────────────────────────────┘
 │
 ▼
┌─────────────────────────────┐
│ 모든 임베딩 파일 로드         │
│ - load_embedding_file()      │
│ - 데이터 병합                │
└─────────────────────────────┘
 │
 ▼
┌─────────────────────────────┐
│ save_to_collection()         │
└─────────────────────────────┘
 │
 ├─→ create_or_get_collection()
 │    └─→ 컬렉션 생성/가져오기
 │
 ├─→ 기존 ID 확인
 │    └─→ 중복 방지
 │
 ├─→ 데이터 준비
 │    ├─→ ids
 │    ├─→ embeddings
 │    ├─→ documents
 │    └─→ metadatas
 │
 └─→ 배치 단위로 저장
      ├─→ collection.add()
      └─→ 배치 크기: 1000
 │
 ▼
┌─────────────────────────────┐
│ verify_collection()          │
│ - 컬렉션 정보 확인            │
│ - 샘플 데이터 확인            │
└─────────────────────────────┘
 │
 ▼
결과 출력 및 완료
```

### 저장 상세 흐름

```
임베딩 데이터
 │
 ▼
┌─────────────────────┐
│ 기존 ID 확인         │
│ (중복 방지)          │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ 데이터 준비          │
│ - ids               │
│ - embeddings        │
│ - documents         │
│ - metadatas         │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ 배치 분할            │
│ (batch_size=1000)   │
└─────────────────────┘
 │
 ▼
┌─────────────────────┐
│ ChromaDB 저장        │
│ collection.add()    │
└─────────────────────┘
 │
 ▼
Vector DB 저장 완료
```

---

## 주요 설정값

### create_chunk_files.py
- `max_tokens`: 500
- `overlap_ratio`: 0.1 (10%)

### create_openai_embeddings.py
- `MODEL_NAME`: "text-embedding-3-large"
- `BATCH_SIZE`: 100

### save_to_vectordb.py
- `collection_name`: "vector_adler"
- `batch_size`: 1000
- `similarity_metric`: "cosine"

---

## 에러 처리

### automatic_save.py
- 각 단계 실패 시 `rollback()` 호출
- 생성된 디렉토리 자동 삭제

### create_chunk_files.py
- 파일 없음 → 건너뛰기
- JSON 파싱 오류 → 예외 처리

### create_openai_embeddings.py
- API 키 없음 → 오류 메시지
- 배치 처리 실패 → 빈 임베딩으로 채우기

### save_to_vectordb.py
- 중복 ID → 건너뛰기
- 배치 저장 실패 → 다음 배치 계속 진행
- 컬렉션 검증 실패 → 오류 메시지

