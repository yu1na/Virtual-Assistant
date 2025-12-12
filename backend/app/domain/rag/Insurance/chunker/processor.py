"""
Advanced Semantic Chunking with Overlap and Metadata
고급 의미 기반 청킹:
1. 문장 분할 (NLTK)
2. 제목/섹션 인식
3. 문장 임베딩 (OpenAI text-embedding-3-large)
4. 유사도 계산 (Cosine similarity)
5. 의미 경계 감지 + 섹션 경계
6. 청크 생성 + 오버랩 적용
7. 표 처리 및 메타데이터 추가
8. 품질 검증 및 정규화
"""
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import json
import re
from collections import defaultdict
import numpy as np
from nltk.tokenize import sent_tokenize
from openai import OpenAI

from .config import MAX_TOKENS, OVERLAP_TOKENS
from .utils import (
    generate_uuid, tokenize, detokenize, get_logger,
    resolve_input_path, resolve_output_path, save_json, load_json
)

logger = get_logger(__name__)

# OpenAI 클라이언트 초기화
client = OpenAI()

# 상수
EMBEDDING_MODEL = "text-embedding-3-large"  # 업그레이드: small → large
SIMILARITY_THRESHOLD = 0.5
MIN_CHUNK_TOKENS = 20  # 너무 작은 청크 병합
MAX_CHUNK_TOKENS = MAX_TOKENS  # 1024
OVERLAP_PERCENTAGE = 0.10  # 10% 오버랩


# ============================================================================
# STEP 1: LOAD & NORMALIZE & EXTRACT METADATA
# ============================================================================
def load_pages(extracted_json_path: Path) -> List[Dict[str, Any]]:
    """Load pages from extractor output JSON"""
    data = load_json(extracted_json_path)
    return data.get("pages", [])


def detect_heading(text: str) -> Tuple[bool, int]:
    """
    제목 판별 및 레벨 감지
    Returns: (is_heading, level)
    """
    stripped = text.strip()
    if not stripped:
        return False, 0
    
    # 레벨 1: Ⅰ, Ⅱ, ... (로마 숫자) - 혼자 있는 경우도 인정
    if re.match(r"^[Ⅰ-Ⅻ](\s|$)", stripped):
        return True, 1
    
    # 레벨 2: 1., 2., ... (숫자+점) 또는 그냥 숫자만
    if re.match(r"^\d+\.", stripped) or (len(stripped) <= 3 and stripped.isdigit()):
        return True, 2
    
    # 레벨 3: 가. 나. ... (한글 나열) - 한 글자 한글자 + 점
    if re.match(r"^[가-힣]\.", stripped):
        return True, 3
    
    # 레벨 4: (1), (2), ... (괄호 숫자)
    if re.match(r"^\(\d+\)", stripped):
        return True, 4
    
    # 특수: "목차", "목 차" 등
    if stripped.startswith("목") and ("차" in stripped or "록" in stripped):
        return True, 1
    
    return False, 0


def normalize_text(text: str) -> str:
    """Normalize text while preserving tables and markdown"""
    lines = text.splitlines()
    out_lines: List[str] = []
    
    for ln in lines:
        # Preserve table and list lines
        if "|" in ln or ln.strip().startswith("*"):
            out_lines.append(ln)
        else:
            s = ln.replace("\t", " ")
            s = re.sub(r"\s+", " ", s)
            out_lines.append(s.strip())
    
    normalized = "\n".join(out_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def normalize_pages(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize all pages and extract metadata"""
    normalized = []
    current_section_title = ""
    current_subsection = ""
    
    for p in pages:
        page_num = p.get("page")
        content = p.get("content", "")
        tables_markdown = p.get("tables_markdown", [])
        
        # 첫 문장이 제목인지 확인 (섹션 추적)
        first_sentence = content.split("\n")[0] if content else ""
        is_heading, level = detect_heading(first_sentence)
        if is_heading:
            if level == 1:
                current_section_title = first_sentence.strip()
                current_subsection = ""
            elif level == 2:
                current_subsection = first_sentence.strip()
        
        normalized.append({
            "page": page_num,
            "content": normalize_text(content),
            "tables_markdown": tables_markdown,
            "section_title": current_section_title,
            "subsection": current_subsection,
            "has_tables": len(tables_markdown) > 0,
        })
    
    return normalized


# ============================================================================
# STEP 2: SENTENCE SEGMENTATION WITH METADATA
# ============================================================================
def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK"""
    sentences = sent_tokenize(text)
    # Filter out empty sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences


def create_page_sentences(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Split each page into sentences with metadata tracking
    각 문장에 페이지, 섹션, 제목 정보 포함
    """
    page_sentences = []
    
    for page in pages:
        page_num = page.get("page")
        text = page.get("content", "")
        section_title = page.get("section_title", "")
        subsection = page.get("subsection", "")
        has_tables = page.get("has_tables", False)
        
        if not text.strip():
            continue
        
        sentences = split_into_sentences(text)
        for sent in sentences:
            is_heading, heading_level = detect_heading(sent)
            
            # 새 섹션 발견 시 업데이트
            if is_heading:
                if heading_level == 1:
                    section_title = sent.strip()
                    subsection = ""
                elif heading_level == 2:
                    subsection = sent.strip()
            
            page_sentences.append({
                "sentence": sent,
                "page": page_num,
                "section_title": section_title,
                "subsection": subsection,
                "heading_level": heading_level if is_heading else 0,
                "is_heading": is_heading,
                "has_tables": has_tables,
                "embedding": None,
            })
    
    return page_sentences


# ============================================================================
# STEP 3: EMBEDDING
# ============================================================================
def embed_sentences(page_sentences: List[Dict[str, Any]], batch_size: int = 100) -> List[Dict[str, Any]]:
    """
    Embed sentences using OpenAI text-embedding-3-large
    배치 처리로 효율성 극대화
    """
    sentences_to_embed = [s["sentence"] for s in page_sentences]
    total = len(sentences_to_embed)
    
    logger.info(f"Embedding {total} sentences with {EMBEDDING_MODEL}...")
    
    # 배치 처리
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = sentences_to_embed[batch_start:batch_end]
        
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=1536,  # text-embedding-3-large의 차원
            )
            
            for i, embedding_data in enumerate(response.data):
                page_sentences[batch_start + i]["embedding"] = embedding_data.embedding
            
            if batch_end % (batch_size * 5) == 0 or batch_end == total:
                logger.info(f"  {batch_end}/{total} embedded")
        
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise
    
    return page_sentences


# ============================================================================
# STEP 4: SIMILARITY & BOUNDARY DETECTION
# ============================================================================
def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a_arr = np.array(a)
    b_arr = np.array(b)
    
    dot_product = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(dot_product / (norm_a * norm_b))


def detect_semantic_boundaries(
    page_sentences: List[Dict[str, Any]],
    threshold: float = SIMILARITY_THRESHOLD
) -> List[int]:
    """
    의미적 경계 감지
    - 연속 문장 간 유사도 계산
    - 유사도가 threshold 이하로 떨어지는 지점을 경계로 표시
    - 제목 이전도 자동으로 경계 표시
    """
    if len(page_sentences) <= 1:
        return []
    
    boundaries = [0]  # 첫 문장은 항상 시작
    
    for i in range(len(page_sentences) - 1):
        current = page_sentences[i]
        next_sent = page_sentences[i + 1]
        
        # 제목 이전은 항상 경계
        if next_sent["is_heading"]:
            boundaries.append(i + 1)
            continue
        
        # 페이지 경계
        if current["page"] != next_sent["page"]:
            boundaries.append(i + 1)
            continue
        
        # 임베딩이 있는 경우 유사도 계산
        if current["embedding"] and next_sent["embedding"]:
            sim = cosine_similarity(current["embedding"], next_sent["embedding"])
            if sim < threshold:
                boundaries.append(i + 1)
    
    boundaries.append(len(page_sentences))  # 마지막 문장
    
    # 정렬 및 중복 제거
    return sorted(list(set(boundaries)))


# ============================================================================
# STEP 5: TABLE HANDLING
# ============================================================================
def extract_table_chunks(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    표를 별도의 청크로 추출
    표는 문맥과 함께 포함되어야 함
    """
    table_chunks = []
    
    for page in pages:
        tables = page.get("tables_markdown", [])
        if not tables:
            continue
        
        page_num = page.get("page")
        section_title = page.get("section_title", "")
        subsection = page.get("subsection", "")
        
        for table_idx, table_md in enumerate(tables):
            tokens = tokenize(table_md)
            token_count = len(tokens)
            
            chunk = {
                "chunk_id": generate_uuid("ins"),
                "content": table_md,
                "tokens": token_count,
                "source_pages": [page_num],
                "semantic_group": -1,  # 표는 별도 처리
                "part": 1,
                "chunk_type": "table",
                "has_tables": True,
                "section_level": 0,
                "section_title": section_title,
                "subsection": subsection,
                "table_index": table_idx,
                "previous_chunk_id": None,
                "next_chunk_id": None,
            }
            table_chunks.append(chunk)
    
    return table_chunks


# ============================================================================
# STEP 6: CHUNK CREATION WITH OVERLAP
# ============================================================================
def create_chunks(
    page_sentences: List[Dict[str, Any]],
    boundaries: List[int],
    max_tokens: int = MAX_CHUNK_TOKENS
) -> List[Dict[str, Any]]:
    """
    의미 경계에서 청크 생성
    - 오버랩 적용 (인접 청크 간)
    - 너무 작은 청크는 병합
    - 너무 큰 청크는 재분할
    - 메타데이터 추가
    """
    chunks = []
    
    # 의미 경계에 따라 먼저 청크 생성
    raw_chunks = []
    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1]
        
        chunk_sentences = page_sentences[start_idx:end_idx]
        if not chunk_sentences:
            continue
        
        chunk_text = " ".join([s["sentence"] for s in chunk_sentences])
        chunk_pages = sorted(list(set([s["page"] for s in chunk_sentences])))
        
        # 메타데이터 수집
        section_titles = list(set([s["section_title"] for s in chunk_sentences if s["section_title"]]))
        subsections = list(set([s["subsection"] for s in chunk_sentences if s["subsection"]]))
        has_heading = any(s["is_heading"] for s in chunk_sentences)
        
        tokens = tokenize(chunk_text)
        token_count = len(tokens)
        
        raw_chunks.append({
            "sentences": chunk_sentences,
            "text": chunk_text,
            "pages": chunk_pages,
            "tokens": token_count,
            "semantic_group": i,
            "section_titles": section_titles,
            "subsections": subsections,
            "has_heading": has_heading,
        })
    
    # 너무 작은 청크 병합 및 오버랩 적용
    merged_chunks = []
    skip_idx = set()
    
    for idx in range(len(raw_chunks)):
        if idx in skip_idx:
            continue
        
        chunk = raw_chunks[idx]
        
        # 너무 작으면 다음 청크와 병합
        if chunk["tokens"] < MIN_CHUNK_TOKENS and idx + 1 < len(raw_chunks):
            next_chunk = raw_chunks[idx + 1]
            merged_text = chunk["text"] + " " + next_chunk["text"]
            merged_tokens = tokenize(merged_text)
            
            merged_chunk = {
                "sentences": chunk["sentences"] + next_chunk["sentences"],
                "text": merged_text,
                "pages": sorted(list(set(chunk["pages"] + next_chunk["pages"]))),
                "tokens": len(merged_tokens),
                "semantic_group": chunk["semantic_group"],
                "section_titles": list(set(chunk["section_titles"] + next_chunk["section_titles"])),
                "subsections": list(set(chunk["subsections"] + next_chunk["subsections"])),
                "has_heading": chunk["has_heading"] or next_chunk["has_heading"],
            }
            merged_chunks.append(merged_chunk)
            skip_idx.add(idx + 1)
        else:
            merged_chunks.append(chunk)
    
    # 오버랩 적용하여 최종 청크 생성
    for chunk_idx, chunk in enumerate(merged_chunks):
        # 기본 청크
        if chunk["tokens"] <= max_tokens:
            # 오버랩 토큰 계산
            overlap_tokens_count = max(1, int(chunk["tokens"] * OVERLAP_PERCENTAGE))
            
            chunks.append({
                "chunk_id": generate_uuid("ins"),
                "content": chunk["text"],
                "tokens": chunk["tokens"],
                "source_pages": chunk["pages"],
                "semantic_group": chunk["semantic_group"],
                "part": 1,
                "chunk_type": "text",
                "has_tables": any(s["has_tables"] for s in chunk["sentences"]),
                "section_level": max([s["heading_level"] for s in chunk["sentences"]], default=0),
                "section_title": chunk["section_titles"][0] if chunk["section_titles"] else "",
                "subsection": chunk["subsections"][0] if chunk["subsections"] else "",
                "next_chunk_overlap_tokens": overlap_tokens_count,  # 다음 청크와의 오버랩 정보
                "previous_chunk_id": None,
                "next_chunk_id": None,
            })
        else:
            # 토큰 오버플로우 시 재분할
            tokens = tokenize(chunk["text"])
            start = 0
            part = 1
            
            while start < len(tokens):
                end = min(start + max_tokens, len(tokens))
                part_tokens = tokens[start:end]
                part_content = detokenize(part_tokens)
                
                chunks.append({
                    "chunk_id": generate_uuid("ins"),
                    "content": part_content,
                    "tokens": len(part_tokens),
                    "source_pages": chunk["pages"],
                    "semantic_group": chunk["semantic_group"],
                    "part": part,
                    "chunk_type": "text",
                    "has_tables": any(s["has_tables"] for s in chunk["sentences"]),
                    "section_level": max([s["heading_level"] for s in chunk["sentences"]], default=0),
                    "section_title": chunk["section_titles"][0] if chunk["section_titles"] else "",
                    "subsection": chunk["subsections"][0] if chunk["subsections"] else "",
                    "next_chunk_overlap_tokens": 0,
                    "previous_chunk_id": None,
                    "next_chunk_id": None,
                })
                
                part += 1
                start = end
    
    # 청크 링크 추가 (prev/next)
    for i in range(len(chunks)):
        chunks[i]["previous_chunk_id"] = chunks[i - 1]["chunk_id"] if i > 0 else None
        chunks[i]["next_chunk_id"] = chunks[i + 1]["chunk_id"] if i < len(chunks) - 1 else None
    
    return chunks


# ============================================================================
# STEP 7: QUALITY VALIDATION
# ============================================================================
def validate_and_normalize_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    청크 품질 검증
    - 너무 작은 청크 제거
    - 통계 정보 추가
    """
    validated = []
    skipped = 0
    
    for chunk in chunks:
        # 너무 작은 청크는 무시 (1토큰 이상만 유효)
        if chunk["tokens"] < 1:
            skipped += 1
            continue
        
        validated.append(chunk)
    
    if skipped > 0:
        logger.info(f"Skipped {skipped} invalid chunks")
    
    return validated


# ============================================================================
# MAIN PIPELINE
# ============================================================================
def process_file(pdfname: str, similarity_threshold: float = SIMILARITY_THRESHOLD) -> Path:
    """
    메인 파이프라인:
    1. 추출된 JSON 로드
    2. 텍스트 정규화 + 섹션 추적
    3. 문장 분할 + 메타데이터
    4. 임베딩 생성 (text-embedding-3-large)
    5. 의미 경계 감지
    6. 청크 생성 (오버랩 적용)
    7. 표 처리
    8. 품질 검증
    """
    input_path = resolve_input_path(pdfname)
    output_path = resolve_output_path(pdfname)
    
    logger.info(f"Processing {pdfname} with advanced semantic chunking...")
    
    # Load & Normalize
    pages = load_pages(input_path)
    pages = normalize_pages(pages)
    logger.info(f"Loaded {len(pages)} pages")
    
    # Sentence Segmentation
    page_sentences = create_page_sentences(pages)
    logger.info(f"Split into {len(page_sentences)} sentences")
    
    # Embedding
    page_sentences = embed_sentences(page_sentences)
    
    # Boundary Detection
    boundaries = detect_semantic_boundaries(page_sentences, threshold=similarity_threshold)
    logger.info(f"Detected {len(boundaries) - 1} semantic groups")
    
    # Create Chunks
    chunks = create_chunks(page_sentences, boundaries, max_tokens=MAX_CHUNK_TOKENS)
    logger.info(f"Created {len(chunks)} chunks (with overlap)")
    
    # Extract Tables
    table_chunks = extract_table_chunks(pages)
    chunks.extend(table_chunks)
    logger.info(f"Added {len(table_chunks)} table chunks")
    
    # Validate
    chunks = validate_and_normalize_chunks(chunks)
    
    # Save
    save_json(output_path, chunks)
    logger.info(f"Chunks saved: {output_path} (count={len(chunks)})")
    
    return output_path


def run_for_all() -> List[Path]:
    """Process all PDFs in the proceeds directory"""
    input_dir = Path(__file__).parent.parent / "documents" / "proceeds"
    
    extracted_files = list(input_dir.glob("*_extracted.json"))
    outputs = []
    
    for extracted_file in extracted_files:
        pdfname = extracted_file.stem.replace("_extracted", "")
        try:
            output = process_file(pdfname)
            outputs.append(output)
        except Exception as e:
            logger.error(f"Error processing {pdfname}: {e}")
            raise
    
    return outputs
