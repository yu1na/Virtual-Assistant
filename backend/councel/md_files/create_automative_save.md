<!-- 생성일 2025.11.24 16:11 -->

# Task
- ``create_chunck_files.py`` 파일과 ``create_openai_embeddings.py`` 파일과 ``save_to_vector_db.py`` 파일을 사용하여 하나로 합치는 Python 스크립트를 생성한다.

# Input
- ``create_chunck_files.py``
- ``create_openai_embeddings.py``
- ``save_to_vector_db.py``
- 이 세개의 파일을 하나로 합치는 Python 스크립트를 생성한다

# Rules
- 세개의 파일들 안에 있는 코드를 **재사용**하는 것이 아니라 각각의 파일을 한 파일에서 **호출**하는 방식으로 구현한다.
- 만약 ``backend/councel/adler/chunkfiles`` 폴더와 ``backend/councel/adler/embeddings`` 폴더가 존재하지 않으면 생성한다.
- 만약 ``backend/councel/adler/chunfiles`` 폴더 안에 청크파일이 없을 경우 ``create_chunck_files.py`` 파일을 실행하여 청크파일을 생성한다.
- 만약 ``backend/councel/adler/embeddings`` 폴더 안에 임베딩 파일이 없을 경우 ``create_openai_embeddings.py`` 파일을 실행하여 임베딩 파일을 생성한다.
- 만약 ``backend/councel/adler/vector_db`` 폴더가 존재하지 않으면 ``save_to_vector_db.py`` 파일을 실행하여 Vector DB 안에 임베딩 파일을 저장한다.

# Output Format
- Python 스크립트 파일은 ``backend/councel/sourcecode`` 폴더 안에 ``automatic_save.py`` 파일로 저장한다
- ``automatic_save.py`` 파일은 다른 파일에서 호출할 예정이므로 함수로 구현한다.
- ``automatic_save.py`` 파일을 단독적으로 실행했을때도 정상적으로 작동하도록 구현한다.