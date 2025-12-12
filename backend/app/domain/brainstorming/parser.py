"""
브레인스토밍 청크 파일 파싱 모듈

이 모듈은 Markdown 형식의 청크 파일을 파싱하여 
개별 청크로 분리하고 JSON 형태로 저장합니다.
"""
import re
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class ChunkParser:
    """청크 파일을 파싱하는 클래스"""
    
    def __init__(self):
        # 현재 파일의 위치를 기준으로 data 디렉토리 경로 설정
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.prompts_dir = self.data_dir / "prompts"
        self.embeddings_dir = self.data_dir / "embeddings"
        
    def parse_chunks(self, file_path: str = None) -> List[Dict]:
        """
        청크 파일을 파싱하여 리스트로 반환
        
        Args:
            file_path: 파싱할 파일 경로 (기본값: data/prompts/ChunkBrainstormingTechniques.md)
            
        Returns:
            파싱된 청크들의 리스트
            [
                {
                    "chunk_id": "01",
                    "title": "마인드 매핑",
                    "content": "수행 방식: ...",
                    "metadata": {
                        "created_at": "2025-11-17T...",
                        "word_count": 150
                    }
                },
                ...
            ]
        """
        # 기본 파일 경로 설정
        if file_path is None:
            file_path = self.prompts_dir / "ChunkBrainstormingTechniques.md"
        else:
            file_path = Path(file_path)
            
        # 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 청크 분리 (# [CHUNK XX] 패턴으로 분리)
        # 정규식 설명:
        # - # \[CHUNK (\d+)\]: CHUNK 헤더를 찾고, 숫자를 캡처
        # - (?:\n|$): 줄바꿈 또는 파일 끝
        chunk_pattern = r'# \[CHUNK (\d+)\]\n(.*?)(?=# \[CHUNK \d+\]|$)'
        matches = re.findall(chunk_pattern, content, re.DOTALL)
        
        chunks = []
        for chunk_id, chunk_content in matches:
            # 청크 내용 정리
            chunk_content = chunk_content.strip()
            
            # 제목 추출 (첫 번째 줄 또는 첫 번째 문단)
            lines = chunk_content.split('\n')
            title = lines[0].strip() if lines else f"청크 {chunk_id}"
            
            # 청크 데이터 구성
            chunk_data = {
                "chunk_id": chunk_id.zfill(2),  # "1" -> "01"
                "title": title,
                "content": chunk_content,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "word_count": len(chunk_content),
                    "char_count": len(chunk_content),
                    "source_file": file_path.name
                }
            }
            
            chunks.append(chunk_data)
        
        return chunks
    
    def save_to_json(self, chunks: List[Dict], output_filename: str = "parsed_chunks.json"):
        """
        파싱된 청크를 JSON 파일로 저장
        
        Args:
            chunks: 파싱된 청크 리스트
            output_filename: 출력 파일명 (기본값: parsed_chunks.json)
        """
        output_path = self.embeddings_dir / output_filename
        
        # embeddings 디렉토리가 없으면 생성
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {len(chunks)}개의 청크가 저장되었습니다: {output_path}")
        return output_path
    
    def process(self, file_path: str = None, output_filename: str = "parsed_chunks.json"):
        """
        파싱부터 저장까지 전체 프로세스 실행
        
        Args:
            file_path: 입력 파일 경로
            output_filename: 출력 파일명
            
        Returns:
            저장된 파일 경로
        """
        print("📄 청크 파일 파싱 시작...")
        chunks = self.parse_chunks(file_path)
        print(f"✅ {len(chunks)}개의 청크를 파싱했습니다.")
        
        print("\n💾 JSON 파일로 저장 중...")
        output_path = self.save_to_json(chunks, output_filename)
        
        # 통계 출력
        print("\n📊 파싱 결과:")
        print(f"   - 총 청크 수: {len(chunks)}")
        print(f"   - 평균 글자 수: {sum(c['metadata']['char_count'] for c in chunks) // len(chunks)}")
        print(f"   - 저장 위치: {output_path}")
        
        return output_path


# 테스트 실행용 코드
if __name__ == "__main__":
    parser = ChunkParser()
    parser.process()

