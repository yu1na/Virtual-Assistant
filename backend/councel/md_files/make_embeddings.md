<!-- 생성일 2025.11.21 11:39 -->

# Task
OpenAI 임베딩 모델을 사용하여 **청크 파일(.jsonl, .txt 등)을 읽고 임베딩을 생성하여 결과를 저장하는 Python 스크립트**를 작성하라.

# Input
- 입력 청크 파일 경로
  - ``backend/councel/dataset/adler/chunkfiles`` 안에 있는 파일들을 모두 임베딩 파일로 변환한다.
- 출력 임베딩 파일 경로
  - ``backend/councel/dataset/adler/embeddings`` 안에 저장한다.(폴더가 없다면 생성한다)
- 사용할 OpenAI 임베딩 모델 이름 (예: `text-embedding-3-large`)
- OpenAI API 키는 환경 변수 `OPENAI_API_KEY` 를 통해 로드

# Rules
1. **Python 3.10 이상** 기준으로 작성할 것.
2. **OpenAI SDK**를 사용하여 임베딩을 생성할 것.
3. 임베딩 생성 시 토크나이저 호출은 개발자가 따로 하지 않으며, **OpenAI가 자동으로 처리**함.
4. CUDA/GPU 설정은 필요 없음 (**OpenAI API는 GPU 사용 불가**).**
5. 임베딩 결과는 **JSON 파일**로 저장하기 위해서는 **NumPy 배열**을 **Python 리스트**로 변환 (**JSON 직렬화 가능**)해야 한다.
6. try-except로 예외 처리를 포함할 것.
7. 파일 저장은 ``backend/councel/sourcecode/automatic_save/create_embedding_files.py``에 저장한다.

# Algorithm
1. 입력 청크 파일 로드  
2. OpenAI 임베딩 API 호출  
   - 모델: 입력된 모델 이름 사용  
   - 각 청크 텍스트에 대해 임베딩 생성
3. 생성된 임베딩을 리스트로 저장
4. JSON 파일로 결과 저장
5. 처리 완료 메시지 출력

# Output Format
- 완성된 Python 스크립트 전체 코드
- 코드에는 다음 함수가 반드시 포함되어야 한다:
  - `load_chunks(file_path)`
  - `create_embeddings(chunks, model_name)`
  - `save_embeddings(embeddings, output_path)`
  - `main()`
