<!-- 생성일 2025.11.19 15:31 -->

# Task
- **Input**으로 주어진 *pdf*파일을 **json**형태의 청크파일로 변환하는 작업을 수행한다.

# Input
- ``backend/councel/dataset/adler/case`` 안에 있는 파일들을 모두 청크파일로 변환한다.
- ``backend/councel/dataset/adler/theory`` 안에 있는 파일들을 모두 청크파일로 변환한다.
- ``backend/councel/dataset/adler/interventions`` 안에 있는 파일들을 모두 청크파일로 변환한다.
- ``backend/councel/dataset/adler/qna`` 안에 있는 파일들을 모두 청크파일로 변환한다.
- ``backend/councel/dataset/adler/tone`` 안에 있는 파일들을 모두 청크파일로 변환한다.

# Rules
- **정제화 알고리즘**에 들어가야 하는 내용
  - *패턴 삭제*
  - *표나 그래프 글자가 아닌 것들 다 삭제*
  - *뒷부분 삭제*
  - *청크 설정*
  - *단어-하이픈 복원*
  - *페이지 번호 제거*
  - *한글 제거*
  - *반복되는 특수문자 제거* (예: ====, ----, ...., 등)
- **PDF 추출**은 *PyMuPDF(fitz)*를 사용한다.
- **청크 방식**
  - **의미 기반** 청킹 + **헤더 기반** 청킹 사용
    - 헤더 발견 → 새 청크 시작
    - 헤더 없는 일반 테스트 → 의미 기반으로 분리
    - 청크 기준 → *500*토큰
- 파일 저장은 ``backend/councel/sourcecode/automatic_save/create_chunkfis.py``에 저장한다
- 생성된 청크 파일은 **json**파일로 저장한다.
- 생성된 청크 파일은 ``backend/councel/dataset/adler/chunkfiles`` 안에 저장한다.

# Output Format

```json
{
  "id": "rogers_001",
  "text": "아들러는 개인중심 상담 이론의 핵심은...",
  "metadata": {
    "source": "adler_theory_1.pdf",
    "author": "Adler",
    "category": "theory",
    "topic": "client-centered therapy",
    "year": "1951",
    "tags": ["아들러", "개인중심", "상담이론"],
    "chunk_index": 1,
    "total_chunks": 38
  }
}