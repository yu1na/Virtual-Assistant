#!/usr/bin/env python
"""
Insurance Extractor 통계 분석 스크립트
실제 PDF 추출 후 페이지별 모드 분류
"""

import sys
import json
from pathlib import Path
from collections import Counter

# 프로젝트 루트 경로
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.domain.rag.Insurance.extractor.pdf_extractor import PDFExtractor
from app.domain.rag.Insurance.extractor.file_manager import resolve_input_pdfs


def analyze_extraction_results():
    """PDF 추출 후 결과 분석"""
    print("\n" + "="*70)
    print("Insurance Extractor 통계 분석")
    print("="*70)
    
    # PDF 추출
    pdfs = resolve_input_pdfs()
    if not pdfs:
        print("⚠ 추출할 PDF가 없습니다.")
        return
    
    print(f"\n찾은 PDF: {len(pdfs)}개")
    for pdf in pdfs:
        print(f"  - {pdf.name}")
    
    extractor = PDFExtractor()
    
    # 통계 수집
    all_stats = {
        "blank": 0,
        "text_only": 0,
        "text_with_table": 0,
        "ocr_recommended": 0,
    }
    
    variation_scores = []
    
    print("\n" + "="*70)
    print("PDF 추출 진행 중...")
    print("="*70)
    
    for pdf in pdfs[:1]:  # 첫 번째 PDF만 처리
        print(f"\n처리 중: {pdf.name}")
        
        try:
            output_path = extractor.extract(str(pdf))
            
            if not output_path.exists():
                print(f"  ✗ 출력 파일 없음: {output_path}")
                continue
            
            # 추출 결과 로드
            with open(output_path, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            pages = result.get("pages", [])
            print(f"  총 페이지: {len(pages)}")
            
            # 페이지별 분석
            for page in pages:
                mode = page.get("mode", "unknown")
                has_tables = page.get("has_tables", False)
                use_ocr = page.get("use_ocr", False)
                variation_score = page.get("variation_score", 0)
                
                if variation_score:
                    variation_scores.append(variation_score)
                
                # 분류 (상호 배타적)
                if mode == "blank":
                    all_stats["blank"] += 1
                elif has_tables:
                    all_stats["text_with_table"] += 1
                else:
                    all_stats["text_only"] += 1
                
                # OCR 권장은 별도로 카운트 (위와 동시에 가능)
                if use_ocr:
                    all_stats["ocr_recommended"] += 1
            
        except Exception as e:
            print(f"  ✗ 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # 결과 출력
    print("\n" + "="*70)
    print("추출 결과 통계")
    print("="*70)
    
    # 페이지 분류 (상호 배타적)
    total_classified = all_stats['blank'] + all_stats['text_only'] + all_stats['text_with_table']
    
    print(f"\n[전체 페이지 분류]")
    print(f"  전체: {total_classified}개")
    print(f"  ├─ 빈 페이지 (Blank):      {all_stats['blank']:4d} ({all_stats['blank']/max(total_classified,1)*100:5.1f}%)")
    print(f"  ├─ 텍스트 + 표:           {all_stats['text_with_table']:4d} ({all_stats['text_with_table']/max(total_classified,1)*100:5.1f}%)")
    print(f"  └─ 텍스트만:              {all_stats['text_only']:4d} ({all_stats['text_only']/max(total_classified,1)*100:5.1f}%) ← OCR 판단 대상")
    
    print(f"\n[텍스트만 페이지에서의 OCR 판단] ({all_stats['text_only']}개)")
    print(f"  OCR 필요:  {all_stats['ocr_recommended']:4d}개 ({all_stats['ocr_recommended']/max(all_stats['text_only'],1)*100:5.1f}%)")
    print(f"  OCR 불필요: {all_stats['text_only'] - all_stats['ocr_recommended']:4d}개 ({(all_stats['text_only'] - all_stats['ocr_recommended'])/max(all_stats['text_only'],1)*100:5.1f}%)")
    
    # Variation Score 통계
    if variation_scores:
        print(f"\nVariation Score 통계:")
        print(f"  ├─ 평균:   {sum(variation_scores)/len(variation_scores):.3f}")
        print(f"  ├─ 최소:   {min(variation_scores):.3f}")
        print(f"  ├─ 최대:   {max(variation_scores):.3f}")
        
        # OCR 경계선 (0.6) 기준
        below_threshold = sum(1 for s in variation_scores if s < 0.6)
        above_threshold = sum(1 for s in variation_scores if s >= 0.6)
        print(f"  ├─ < 0.6 (OCR 불필요): {below_threshold} ({below_threshold/len(variation_scores)*100:.1f}%)")
        print(f"  └─ ≥ 0.6 (OCR 권장):   {above_threshold} ({above_threshold/len(variation_scores)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("분석 완료")
    print("="*70)


if __name__ == "__main__":
    try:
        analyze_extraction_results()
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
