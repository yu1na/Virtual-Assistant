"""
HR RAG Loader
회사 문서(uploads/)를 임베딩하여 ChromaDB에 저장
"""

import sys
from pathlib import Path
from typing import List

from app.domain.rag.HR.vector_store import VectorStore
from app.domain.rag.HR.document_converter import DocumentConverter
from app.domain.rag.HR.pdf_processor import PDFProcessor
from app.domain.rag.HR.schemas import ProcessedDocument, ProcessedContent, ContentType
from app.domain.rag.HR.config import rag_config
from app.core.config import settings


def init_hr_rag() -> bool:
    """
    HR RAG ChromaDB 초기화
    
    - uploads/ 폴더의 PDF/TXT 파일을 읽어서 처리
    - HR embedder로 임베딩 생성
    - hr_documents 컬렉션에 저장
    
    Returns:
        bool: 성공 여부
    """
    print("\n📋 [HR RAG] 초기화 체크...")
    
    try:
        # 1. 경로 설정
        base_dir = Path(__file__).parent.parent.parent.parent  # Virtual-Assistant 루트
        uploads_dir = base_dir / "backend" / "internal_docs" / "uploads"
        
        print(f"   📂 업로드 폴더: {uploads_dir}")
        
        # 업로드 폴더 확인
        if not uploads_dir.exists():
            print(f"   ⚠️  업로드 폴더가 없습니다: {uploads_dir}")
            return False
        
        # 2. VectorStore 초기화 (hr_documents 컬렉션)
        vector_store = VectorStore(collection_name="hr_documents")
        
        # 3. 이미 데이터가 있는지 확인
        current_count = vector_store.count_documents()
        if current_count > 0:
            print(f"   ✅ 이미 존재 ({current_count}개 청크) - 스킵")
            return True
        
        # 4. 업로드 폴더의 파일 목록 가져오기
        pdf_files = list(uploads_dir.glob("*.pdf"))
        txt_files = list(uploads_dir.glob("*.txt"))
        all_files = pdf_files + txt_files
        
        if not all_files:
            print(f"   ⚠️  처리할 파일이 없습니다: {uploads_dir}")
            return False
        
        print(f"   📄 처리할 파일: {len(all_files)}개 (PDF: {len(pdf_files)}, TXT: {len(txt_files)})")
        
        # 5. DocumentConverter 초기화
        converter = DocumentConverter()
        pdf_processor = PDFProcessor()
        
        # 6. 각 파일 처리
        total_chunks = 0
        processed_files = []
        
        for file_path in all_files:
            try:
                print(f"   📖 처리 중: {file_path.name}...")
                
                # 파일 타입에 따라 처리
                if file_path.suffix.lower() == ".pdf":
                    # PDF 처리
                    processed_doc = pdf_processor.process_pdf(str(file_path))
                    # document_converter에서 processed_doc.filename을 document_id로 사용
                elif file_path.suffix.lower() == ".txt":
                    # TXT 파일 처리
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                    
                    # ProcessedContent 생성 (metadata 포함)
                    from app.domain.rag.HR.schemas import DocumentMetadata
                    content = ProcessedContent(
                        page_number=1,
                        content_type=ContentType.TEXT,
                        text=text_content,
                        metadata=DocumentMetadata(
                            filename=file_path.name,
                            page_number=1,
                            content_type=ContentType.TEXT
                        )
                    )
                    
                    # ProcessedDocument 생성
                    # document_converter에서 filename을 document_id로 사용
                    processed_doc = ProcessedDocument(
                        filename=file_path.name,
                        total_pages=1,
                        contents=[content],
                        file_path=str(file_path)
                    )
                else:
                    print(f"   ⚠️  지원하지 않는 파일 형식: {file_path.suffix}")
                    continue
                
                # 청크 생성
                chunks = converter.create_chunks(processed_doc)
                
                if not chunks:
                    print(f"   ⚠️  청크가 생성되지 않았습니다: {file_path.name}")
                    continue
                
                # VectorStore에 추가
                added_count = vector_store.add_chunks(chunks, reuse_embeddings=False)
                total_chunks += added_count
                processed_files.append(file_path.name)
                
                print(f"   ✅ 완료: {file_path.name} ({added_count}개 청크)")
                
            except Exception as e:
                print(f"   ❌ 파일 처리 실패 ({file_path.name}): {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 7. 검증
        final_count = vector_store.count_documents()
        print(f"   ✅ 초기화 완료! ({final_count}개 청크, {len(processed_files)}개 파일)")
        
        if final_count != total_chunks:
            print(f"   ⚠️  경고: 예상({total_chunks})과 실제({final_count}) 청크 수 불일치")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("HR RAG 로더 - 독립 실행")
    print("=" * 60)
    
    result = init_hr_rag()
    
    print("\n" + "=" * 60)
    print(f"결과: {'✅ 성공' if result else '❌ 실패'}")
    print("=" * 60)

