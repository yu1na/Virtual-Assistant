#!/usr/bin/env python
"""
청킹 실행 스크립트
변경된 설정: MAX_TOKENS=384, OVERLAP_TOKENS=80
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.app.domain.rag.Insurance.chunker.chunker import run_for_file

if __name__ == "__main__":
    print("=" * 60)
    print("Insurance 문서 청킹 시작")
    print("설정: MAX_TOKENS=384, OVERLAP_TOKENS=80")
    print("=" * 60)
    
    try:
        output_path = run_for_file('insurance_manual')
        print(f"\n✅ 청킹 완료!")
        print(f"📁 출력 파일: {output_path}")
        
        # 청크 개수 확인
        import json
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            chunk_count = len(data.get('chunks', []))
            print(f"📊 생성된 청크 개수: {chunk_count}")
            
    except FileNotFoundError as e:
        print(f"\n❌ 오류: {e}")
        print("insurance_manual_extracted.json 파일이 존재하는지 확인하세요.")
    except Exception as e:
        print(f"\n❌ 청킹 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
