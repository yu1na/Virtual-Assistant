<!-- 생성일 2025.11.21 12:08 -->

# Task

임베딩된 **청크 파일**을 *Vector DB(Chroma)*에 저장하고, 검색 시 효율적으로 조회할 수 있도록 구성합니다.

# Input

- embedding_file: 임베딩이 저장된 파일 경로 (.json, .npy 등)

- collection_name: DB 내 컬렉션 이름(vector_adler)

- metadata_fields (선택): 각 청크에 추가할 메타데이터 필드


# Rules

- DB 연결이 실패하면 에러 메시지를 출력하고 중단합니다.

- 이미 동일한 컬렉션/ID가 존재하면 덮어쓴다.(존재하지 않을 경우에 생성을 진행한다.)

- 배치 삽입 시 memory 효율을 고려합니다.

- Vector DB에 삽입 후, 인덱스가 자동으로 생성되도록 합니다(Chroma는 컬렉션 내 자동).

- py파일 저장은 ``backend/councel/sourcecode/automatic_save/save_vectordb.py``에 저장한다.

- 컬렉션은 ``backend/councel/vector_db`` 폴더 안에 저장한다.

# Output Format

총 삽입된 벡터 개수

각 배치별 상태 (성공/실패)

DB 접근에 사용할 컬렉션 객체 혹은 핸들