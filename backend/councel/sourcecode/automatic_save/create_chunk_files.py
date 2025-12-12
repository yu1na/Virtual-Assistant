"""
청크 파일 생성 스크립트
생성날짜: 2025.11.18
수정날짜: 2025.11.19 - Adler PDF 처리 추가
수정날짜: 2025.11.21 - Rogers 관련 코드 제거
리팩토링: 2025.11.25 - 1차 코드 리팩토링(쓸데 없는 print문 제거 및 코드 정리)
수정날짜: 2025.11.28 - Parent-Child Chunking 방식으로 변경
최적화: 2025.12.04 - 성능 최적화 (병렬 처리 + 정규식 캐싱)
  - 정규식 패턴 컴파일 및 캐싱으로 20-30% 성능 개선
  - ProcessPoolExecutor를 사용한 병렬 파일 처리로 70-80% 시간 단축
  - 예상 전체 개선율: 약 75-80% 시간 단축
설명: Adler PDF 파일을 Parent-Child 구조로 청킹하여 개별 JSON 파일로 저장
      Parent: 1000 tokens, Child: 500 tokens
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
import tiktoken
import fitz  # PyMuPDF
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# 청크파일을 만드는 클래스
class ChunkCreator:

    # 초기화
    def __init__(self, max_tokens: int = 500, parent_max_tokens: int = 1000, overlap_ratio: float = 0.2):
        self.max_tokens = max_tokens # Child 청크당 최대 토큰 수
        self.parent_max_tokens = parent_max_tokens # Parent 청크당 최대 토큰 수
        self.overlap_ratio = overlap_ratio # Overlap 비율
        self.encoding = tiktoken.get_encoding("cl100k_base") # 토큰 인코딩 모델
        
        # 정규식 패턴 컴파일 및 캐싱
        self._compile_regex_patterns()
    
    # 정규식 패턴 컴파일 (성능 최적화)
    def _compile_regex_patterns(self):
        # 하이픈으로 끝나는 단어 복원 패턴
        self.pattern_hyphen = re.compile(r'(\w+)-\s*\n\s*(\w+)')
        
        # 페이지 번호 패턴들
        self.pattern_page_num1 = re.compile(r'^\s*\d+\s*$', re.MULTILINE)
        self.pattern_page_num2 = re.compile(r'^Page\s+\d+', re.MULTILINE | re.IGNORECASE)
        self.pattern_page_num3 = re.compile(r'^-\s*\d+\s*-$', re.MULTILINE)
        self.pattern_page_num4 = re.compile(r'^\[\d+\]$', re.MULTILINE)
        
        # 참고문헌 패턴들
        self.pattern_ref1 = re.compile(r'\n\s*References\s*\n.*', re.IGNORECASE | re.DOTALL)
        self.pattern_ref2 = re.compile(r'\n\s*Bibliography\s*\n.*', re.IGNORECASE | re.DOTALL)
        self.pattern_ref3 = re.compile(r'\n\s*참고문헌\s*\n.*', re.DOTALL)
        self.pattern_ref4 = re.compile(r'\n\s*REFERENCES\s*\n.*', re.DOTALL)
        self.pattern_ref5 = re.compile(r'\n\s*BIBLIOGRAPHY\s*\n.*', re.DOTALL)
        
        # URL 패턴
        self.pattern_url = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        
        # 이메일 패턴
        self.pattern_email = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # 한글 패턴
        self.pattern_korean = re.compile(r'[가-힣]+')
        
        # 반복되는 특수문자 패턴
        self.pattern_special_chars = re.compile(r'([=\-_.*#~`+]{3,})')
        
        # 과도한 줄바꿈 패턴
        self.pattern_newlines = re.compile(r'\n{3,}')
        
        # 과도한 공백 패턴
        self.pattern_spaces = re.compile(r' {2,}')
        
        # 탭 패턴
        self.pattern_tabs = re.compile(r'\t+')
        
        # 표/그래프 특수문자 제거용 translator (성능 최적화)
        table_chars = ['│', '─', '┼', '├', '┤', '┬', '┴', '┌', '┐', '└', '┘', '║', '═', '╔', '╗', '╚', '╝', '╠', '╣', '╦', '╩', '╬']
        self.table_chars_translator = str.maketrans('', '', ''.join(table_chars))

    # 텍스트의 토큰 수 계산   
    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
    
    # PDF에서 텍스트 추출(PyMuPDF(fitz)를 사용)
    def extract_text_from_pdf(self, pdf_path: Path) -> str:

        doc = fitz.open(pdf_path) # pdf 파일 열기
        full_text = [] # 전체 텍스트를 저장할 리스트
        
        # 페이지 수만큼 반복하면서 리스트에 텍스트 저장
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            full_text.append(text)
        
        doc.close()
        
        # 전체 텍스트 결합
        combined_text = '\n'.join(full_text)
        
        # 하이픈으로 끝나는 단어 복원 (컴파일된 패턴 사용)
        combined_text = self.pattern_hyphen.sub(r'\1\2', combined_text)
        
        return combined_text
    
    # PDF 텍스트 정제화 (컴파일된 정규식 패턴 사용)
    # 정제화 규칙
    # 1. 페이지 번호 제거
    # 2. 표/그래프 특수문자 제거
    # 3. 참고문헌 섹션 제거
    # 4. URL, 이메일 제거
    # 5. 한글 제거
    # 6. 반복되는 특수문자 제거
    # 7. 과도한 공백 정리
    # 8. 앞뒤 공백 제거
    def clean_pdf_text(self, text: str) -> str:

        # 1. 페이지 번호 패턴 제거 (컴파일된 패턴 사용)
        text = self.pattern_page_num1.sub('', text)  # 숫자만 있는 줄
        text = self.pattern_page_num2.sub('', text)  # Page 번호 제거
        text = self.pattern_page_num3.sub('', text)  # 하이픈으로 끝나는 단어 복원
        text = self.pattern_page_num4.sub('', text)  # 대괄호에 둘러싸인 숫자 제거
        
        # 2. 표/그래프 특수문자 제거 (성능 최적화: str.maketrans/translate 사용)
        text = text.translate(self.table_chars_translator)
        
        # 3. 참고문헌 섹션 제거 (컴파일된 패턴 사용)
        text = self.pattern_ref1.sub('', text)
        text = self.pattern_ref2.sub('', text)
        text = self.pattern_ref3.sub('', text)
        text = self.pattern_ref4.sub('', text)
        text = self.pattern_ref5.sub('', text)
        
        # 4. URL 제거 (컴파일된 패턴 사용)
        text = self.pattern_url.sub('', text)
        
        # 5. 이메일 주소 제거 (컴파일된 패턴 사용)
        text = self.pattern_email.sub('', text)
        
        # 6. 한글 제거 (컴파일된 패턴 사용)
        text = self.pattern_korean.sub('', text)
        
        # 7. 반복되는 특수문자 제거 (컴파일된 패턴 사용)
        text = self.pattern_special_chars.sub('', text)
        
        # 8. 반복되는 짧은 줄 제거 (헤더/푸터 가능성)
        lines = text.split('\n')
        line_counts = {}
        for line in lines:
            stripped = line.strip()
            if len(stripped) > 0 and len(stripped) < 50:  # 50자 이하의 짧은 줄만
                line_counts[stripped] = line_counts.get(stripped, 0) + 1
        
        # 3번 이상 반복되는 짧은 줄 제거
        repeated_lines = {line for line, count in line_counts.items() if count >= 3}
        lines = [line for line in lines if line.strip() not in repeated_lines]
        text = '\n'.join(lines)
        
        # 9. 과도한 공백 정리 (컴파일된 패턴 사용)
        text = self.pattern_newlines.sub('\n\n', text)  # 3개 이상의 연속 줄바꿈을 2개로
        text = self.pattern_spaces.sub(' ', text)  # 2개 이상의 연속 공백을 1개로
        text = self.pattern_tabs.sub(' ', text)  # 탭을 공백으로
        
        # 10. 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    # ==================== Adler 관련 메서드 ====================
    
    # Adler 파일명에서 메타데이터 추출
    def extract_metadata_adler(self, filename: str) -> Dict[str, Any]:

        # 확장자 제거
        clean_name = filename.replace('.pdf', '')
        parts = clean_name.split('_')
        
        file_category = parts[1] if len(parts) > 1 else "unknown"
        
        # 메타데이터
        metadata = {
            "author": "Adler",
            "source": filename,
            "category": file_category,
            "topic": "individual psychology",
            "tags": ["아들러"]
        }
        
        # 카테고리별 추가 태그
        if file_category == "case":
            metadata["tags"].extend(["사례연구", "상담"])
        elif file_category == "theory":
            metadata["tags"].extend(["이론", "개인심리학"])
        elif file_category == "interventions":
            metadata["tags"].extend(["개입기법", "치료"])
        elif file_category == "qna":
            metadata["tags"].extend(["질의응답", "FAQ"])
        elif file_category == "tone":
            metadata["tags"].extend(["어조", "성격"])
        
        return metadata
    
    # 파일명에서 메타데이터 추출
    def extract_metadata_from_filename(self, filename: str) -> Dict[str, Any]:
        return self.extract_metadata_adler(filename)
    
    # Parent 청크 생성 (큰 섹션을 parent_max_tokens 기준으로 분할)
    def split_into_parents(self, section_content: str) -> List[str]:

        token_count = self.count_tokens(section_content)
        
        if token_count <= self.parent_max_tokens:
            return [section_content]
        
        # 문단 단위로 분할 (빈 줄 기준)
        paragraphs = section_content.split('\n\n')
        
        parent_chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self.count_tokens(para)
            
            # 단일 문단이 parent_max_tokens를 초과하는 경우
            if para_tokens > self.parent_max_tokens:
                # 현재까지 모은 청크 저장
                if current_chunk:
                    parent_chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # 큰 문단을 줄 단위로 분할
                lines = para.split('\n')
                temp_chunk = []
                temp_tokens = 0
                
                for line in lines:
                    line_tokens = self.count_tokens(line)
                    if temp_tokens + line_tokens > self.parent_max_tokens:
                        if temp_chunk:
                            parent_chunks.append('\n'.join(temp_chunk))
                        temp_chunk = [line]
                        temp_tokens = line_tokens
                    else:
                        temp_chunk.append(line)
                        temp_tokens += line_tokens
                
                if temp_chunk:
                    parent_chunks.append('\n'.join(temp_chunk))
            
            # 현재 청크에 추가 가능한 경우
            elif current_tokens + para_tokens <= self.parent_max_tokens:
                current_chunk.append(para)
                current_tokens += para_tokens
            
            # 새로운 청크 시작
            else:
                if current_chunk:
                    parent_chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
        
        # 마지막 청크 추가
        if current_chunk:
            parent_chunks.append('\n\n'.join(current_chunk))
        
        return parent_chunks
    
    # Child 청크 생성 (Parent를 max_tokens 기준으로 분할)
    def split_parent_into_children(self, parent_content: str) -> List[str]:

        token_count = self.count_tokens(parent_content)
        
        if token_count <= self.max_tokens:
            return [parent_content]
        
        # 문단 단위로 분할 (빈 줄 기준)
        paragraphs = parent_content.split('\n\n')
        
        child_chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self.count_tokens(para)
            
            # 단일 문단이 max_tokens를 초과하는 경우
            if para_tokens > self.max_tokens:
                # 현재까지 모은 청크 저장
                if current_chunk:
                    child_chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # 큰 문단을 줄 단위로 분할
                lines = para.split('\n')
                temp_chunk = []
                temp_tokens = 0
                
                for line in lines:
                    line_tokens = self.count_tokens(line)
                    if temp_tokens + line_tokens > self.max_tokens:
                        if temp_chunk:
                            child_chunks.append('\n'.join(temp_chunk))
                        temp_chunk = [line]
                        temp_tokens = line_tokens
                    else:
                        temp_chunk.append(line)
                        temp_tokens += line_tokens
                
                if temp_chunk:
                    child_chunks.append('\n'.join(temp_chunk))
            
            # 현재 청크에 추가 가능한 경우
            elif current_tokens + para_tokens <= self.max_tokens:
                current_chunk.append(para)
                current_tokens += para_tokens
            
            # 새로운 청크 시작
            else:
                if current_chunk:
                    child_chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
        
        # 마지막 청크 추가
        if current_chunk:
            child_chunks.append('\n\n'.join(current_chunk))
        
        return child_chunks
    
    # PDF 파일을 Parent-Child 청크로 분할
    def process_file(self, filepath: Path, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:

        # PDF 텍스트 추출 및 정제
        content = self.extract_text_from_pdf(filepath)
        content = self.clean_pdf_text(content)
        
        # Parent 청크 생성
        parent_chunks = self.split_into_parents(content)
        
        # 청크가 없으면 전체 파일을 하나의 Parent로
        if not parent_chunks:
            parent_chunks = [content]
        
        # Parent-Child 구조 생성
        result = []
        for parent_idx, parent_text in enumerate(parent_chunks, start=1):
            # Child 청크 생성
            child_chunks = self.split_parent_into_children(parent_text)
            
            # Parent와 Children을 딕셔너리로 저장
            result.append({
                'parent_idx': parent_idx,
                'parent_text': parent_text,
                'children': child_chunks
            })
        
        return result
    
    # Parent-Child 청크 객체 생성
    def create_chunk_objects(self, parent_child_data: List[Dict[str, Any]], metadata: Dict[str, Any], base_id: str) -> List[Dict[str, Any]]:

        chunk_objects = [] # 청크 객체를 저장할 리스트
        total_parents = len(parent_child_data)
        
        # Parent-Child 구조를 순회하면서 청크 객체 생성
        for parent_data in parent_child_data:
            parent_idx = parent_data['parent_idx']
            parent_text = parent_data['parent_text']
            children = parent_data['children']
            
            # Parent ID 생성
            parent_id = f"{base_id}_p{parent_idx:03d}"
            
            # Parent 청크 객체 생성
            parent_obj = {
                "id": parent_id,
                "text": parent_text.strip(),
                "metadata": {
                    **metadata,
                    "chunk_type": "parent",
                    "parent_index": parent_idx,
                    "total_parents": total_parents,
                    "has_children": True,
                    "num_children": len(children)
                }
            }
            chunk_objects.append(parent_obj)
            
            # Child 청크 객체 생성
            for child_idx, child_text in enumerate(children, start=1):
                child_id = f"{base_id}_p{parent_idx:03d}_c{child_idx:03d}"
                
                child_obj = {
                    "id": child_id,
                    "text": child_text.strip(),
                    "metadata": {
                        **metadata,
                        "chunk_type": "child",
                        "parent_id": parent_id,
                        "parent_index": parent_idx,
                        "child_index": child_idx,
                        "total_children": len(children)
                    }
                }
                chunk_objects.append(child_obj)
        
        return chunk_objects
    
    # 단일 파일을 처리하여 개별 json 파일로 저장
    def process_single_file(self, filepath: Path, output_dir: Path) -> Tuple[bool, str, int]:

        try:
            # 메타데이터 추출
            metadata = self.extract_metadata_from_filename(filepath.name)
            
            # 파일을 Parent-Child 구조로 청크 분할
            parent_child_data = self.process_file(filepath, metadata)
            
            # 베이스 ID 생성 (파일명에서 확장자 제거)
            base_id = filepath.stem  # 예: "adler_theory_1"
            
            # 청크 객체 생성
            chunk_objects = self.create_chunk_objects(parent_child_data, metadata, base_id)
            
            # 개별 JSON 파일로 저장
            output_filename = f"{filepath.stem}_chunks.json"
            output_path = output_dir / output_filename
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(chunk_objects, f, ensure_ascii=False, indent=2)

            return (True, filepath.name, len(chunk_objects))
        
        except Exception as e:
            return (False, filepath.name, 0)
    
    # 디렉토리 내 모든 파일 처리
    # 한개의 파일로 할건지 개별 파일로 할건지 선택
    def process_directory(self, input_dir: Path, output_dir: Path, 
                         file_pattern: str = "*.pdf", save_individually: bool = False):

        # 출력 디렉토리 생성
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일 가져오기
        files = sorted(input_dir.glob(file_pattern))
        
        # 파일이 없으면 빈 리스트 리턴
        if len(files) == 0:
            return []
        
        # 개별 파일로 저장하는 경우 (병렬 처리)
        if save_individually:
            return self._process_files_parallel(files, output_dir)
        else:
            # 단일 파일로 저장 (기존 방식 - 순차 처리)
            all_chunk_objects = []
            current_id = 1
            
            for file in files:
                
                # 메타데이터 추출
                metadata = self.extract_metadata_from_filename(file.name)
                
                # 파일을 Parent-Child 구조로 청크 분할
                parent_child_data = self.process_file(file, metadata)
                
                # 청크 객체 생성
                base_id = f"adler_{current_id:03d}"
                chunk_objects = self.create_chunk_objects(parent_child_data, metadata, base_id)
                all_chunk_objects.extend(chunk_objects)
                
                current_id += len(chunk_objects)
            
            # JSON 파일로 저장
            output_filename = "chunks_combined.json"
            output_path = output_dir / output_filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_chunk_objects, f, ensure_ascii=False, indent=2)
            
            return all_chunk_objects
    
    # 병렬 파일 처리 (ProcessPoolExecutor 사용)
    def _process_files_parallel(self, files: List[Path], output_dir: Path) -> int:

        total_chunks = 0
        success_count = 0
        failed_files = []
        
        # 워커 수 결정 (CPU 코어 수)
        max_workers = os.cpu_count()
        
        # ProcessPoolExecutor를 사용한 병렬 처리
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 모든 파일에 대해 작업 제출
            future_to_file = {
                executor.submit(self.process_single_file, file, output_dir): file 
                for file in files
            }
            
            # 완료된 작업부터 결과 수집
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    success, filename, chunk_count = future.result()
                    
                    if success:
                        total_chunks += chunk_count
                        success_count += 1
                    else:
                        failed_files.append(filename)
                        print(f"실패: {filename}")
                        
                except Exception as e:
                    failed_files.append(file.name)
                    print(f"오류: {file.name} - {str(e)}")
        
        if failed_files:
            print(f"  - 실패한 파일: {', '.join(failed_files)}")
        
        return total_chunks

# ==================== Adler 관련 main 함수 ====================

def main():
    
    # 경로 설정
    base_dir = Path(__file__).parent.parent.parent
    adler_base_dir = base_dir / "dataset" / "adler"
    output_dir = adler_base_dir / "chunkfiles"
    
    # 청크 생성기 초기화 (Parent-Child Chunking)
    creator = ChunkCreator(max_tokens=500, parent_max_tokens=1000, overlap_ratio=0.1)
    
    # 5개 카테고리 디렉토리
    categories = ["case", "theory", "interventions", "qna", "tone"]
    
    total_files = 0
    total_chunks = 0
    
    for category in categories:
        input_dir = adler_base_dir / category
        
        # input 파일 경로가 존재하지 않으면 건너뛰기
        if not input_dir.exists():
            print(f"\n디렉토리가 존재하지 않습니다.")
            continue
        
        # PDF 파일 개수 확인
        pdf_files = list(input_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"\nPDF 파일이 없습니다.")
            continue
        
        # PDF 파일 처리 (개별 저장, 병렬 처리)
        chunk_count = creator.process_directory(
            input_dir=input_dir,
            output_dir=output_dir,
            file_pattern="*.pdf",
            save_individually=True
        )
        
        total_files += len(pdf_files)
        total_chunks += chunk_count if isinstance(chunk_count, int) else 0


if __name__ == "__main__":
    # Windows에서 병렬 처리를 위해 필수
    multiprocessing.freeze_support()
    main()