<!-- 생성일 2025.11.24 16:47 -->

# Task
- ``automatic_save.py`` 파일과 ``rag_therapy.py`` 파일을 메인 파일로 합치는 파일을 생성한다.(메인 파일 수정)

# Input
- ``automatic_save.py``
- ``rag_therapy.py``
- 이 두개의 파일을 메인 코드와 합치는 파일을 생성한다.(메인 파일 수정)

# Rules
- 사용자가 채팅창(console X, 채팅창)에 입력한 내용이 심리(영어 한글 상관 X)나 아들러 아니면 심리 상담(나 힘들어, 짜증나, 이런 감정적인 것)과 관련이 있는 내용일 경우에는 ``rag_therapy.py`` 파일을 실행하여 답변을 생성한다.
- 백엔드 서버가 시작할때 ``automatic_save.py`` 파일을 실행하여 Vector DB를 생성한다.
- 필요한 경우 파일을 수정한다.

# Output Format