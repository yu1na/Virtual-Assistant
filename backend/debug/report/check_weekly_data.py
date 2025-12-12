"""Weekly 데이터 확인"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.vector_store_report import get_report_vector_store

# Collection 가져오기
col = get_report_vector_store().get_collection()

# Weekly 문서 샘플 확인
print("="*80)
print("Weekly 문서 샘플")
print("="*80)

try:
    result = col.get(
        limit=3,
        where={"doc_type": "weekly"}
    )
    
    print(f"찾은 문서 수: {len(result['ids'])}")
    print()
    
    for i, (id, metadata, document) in enumerate(zip(result['ids'], result['metadatas'], result['documents'])):
        print(f"[{i+1}] ID: {id}")
        print(f"    Metadata: {metadata}")
        print(f"    Text (처음 200자): {document[:200]}")
        print()
        
except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()

