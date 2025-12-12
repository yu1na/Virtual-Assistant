#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
보험 문서 RAG 성능 평가 스크립트

평가 지표:
1. Retrieval Hit Rate (검색된 chunk에 정답 포함 여부)
2. Embedding 기반 Semantic Similarity
3. LLM-as-a-judge (0~2점 의미 평가)
4. Keyword Hit (핵심 키워드 일치율)
"""

import os
import sys
import json
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

import chromadb
from chromadb.config import Settings
import openai
from openai import OpenAI
import numpy as np
from tqdm import tqdm


# ============================================================================
# 설정
# ============================================================================
CHROMA_DB_PATH = "backend/data/chroma"
COLLECTION_NAME = "insurance_documents"
QA_FILE_PATH = "backend/app/domain/rag/Insurance/tests/qa_filtered_50.json"
OUTPUT_RESULTS_PATH = "backend/app/domain/rag/Insurance/tests/evaluation_results.json"
OUTPUT_CSV_PATH = "backend/app/domain/rag/Insurance/tests/evaluation_results.csv"

# 보험 컬렉션은 text-embedding-3-large 모델로 생성됨
EMBEDDING_MODEL = "text-embedding-3-large"
LLM_MODEL = "gpt-4o-mini"
TOP_K = 5
SIMILARITY_THRESHOLD = 0.75
MIN_KEYWORD_HITS = 2

# OpenAI API Key 로드 (.env 파일 또는 환경변수)
def load_openai_api_key() -> str:
    """OpenAI API Key 로드"""
    # 1. 환경변수에서 시도
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    
    # 2. backend/.env 파일에서 시도
    env_paths = [
        "backend/.env",
        ".env",
        "../../../.env",
        "../../../../.env"
    ]
    
    for env_path in env_paths:
        abs_env_path = os.path.abspath(env_path)
        if os.path.exists(abs_env_path):
            with open(abs_env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('OPENAI_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        if api_key and not api_key.startswith('sk-your-'):
                            return api_key
    
    raise ValueError(
        "OPENAI_API_KEY를 찾을 수 없습니다.\n"
        "다음 중 하나를 수행하세요:\n"
        "1. 환경변수 설정: export OPENAI_API_KEY=sk-...\n"
        "2. backend/.env 파일에 OPENAI_API_KEY=sk-... 추가"
    )

OPENAI_API_KEY = load_openai_api_key()
client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================================
# OpenAI 임베딩 함수 (Chroma 호환)
# ============================================================================
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

def get_openai_embedding_function():
    """Chroma용 OpenAI 임베딩 함수 생성"""
    return OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name=EMBEDDING_MODEL
    )


# ============================================================================
# Chroma DB 로드
# ============================================================================
def load_chroma_collection(db_path: str, collection_name: str):
    """기존 Chroma DB에서 컬렉션 로드"""
    abs_path = os.path.abspath(db_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Chroma DB 경로를 찾을 수 없습니다: {abs_path}")
    
    chroma_client = chromadb.PersistentClient(path=abs_path)
    
    try:
        # OpenAI 임베딩 함수를 사용하여 컬렉션 로드
        embedding_function = get_openai_embedding_function()
        collection = chroma_client.get_collection(
            name=collection_name,
            embedding_function=embedding_function
        )
        count = collection.count()
        print(f"[OK] 컬렉션 '{collection_name}' 로드 완료 (문서 수: {count})")
        return collection
    except Exception as e:
        print(f"[ERROR] 컬렉션 로드 실패: {e}")
        print(f"사용 가능한 컬렉션 목록:")
        for col in chroma_client.list_collections():
            print(f"  - {col.name}")
        raise


# ============================================================================
# OpenAI 임베딩
# ============================================================================
def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> List[float]:
    """텍스트를 임베딩 벡터로 변환"""
    text = text.replace("\n", " ").strip()
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """두 벡터의 코사인 유사도 계산"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# ============================================================================
# Retrieval 함수
# ============================================================================
def retrieve_chunks(collection, query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    """쿼리에 대한 상위 k개 chunk 검색"""
    # Chroma는 자체 임베딩 함수를 사용하므로 텍스트로 직접 쿼리
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    
    chunks = []
    if results and results['documents'] and len(results['documents']) > 0:
        for i in range(len(results['documents'][0])):
            chunk = {
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                'distance': results['distances'][0][i] if results['distances'] else None
            }
            chunks.append(chunk)
    
    return chunks


# ============================================================================
# LLM 답변 생성
# ============================================================================
def generate_llm_answer(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    """검색된 chunk를 기반으로 LLM 답변 생성"""
    context = "\n\n".join([f"[Chunk {i+1}]\n{chunk['text']}" for i, chunk in enumerate(context_chunks)])
    
    prompt = f"""당신은 보험 상품 전문가입니다. 아래 문서를 참고하여 질문에 정확하고 간결하게 답변하세요.

[참고 문서]
{context}

[질문]
{question}

[답변]"""
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "당신은 보험 상품 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"✗ LLM 답변 생성 실패: {e}")
        return ""


# ============================================================================
# LLM-as-a-judge 평가
# ============================================================================
def judge_semantic_match(ground_truth: str, generated_answer: str) -> Tuple[int, str]:
    """LLM을 사용하여 의미적 일치도 평가 (0~2점)"""
    judge_prompt = f"""다음 두 문장이 의미적으로 동일한지 평가하세요.

[정답]
{ground_truth}

[생성된 답변]
{generated_answer}

평가 기준:
- 0점: 의미가 다름
- 1점: 일부 핵심은 맞지만 불완전함
- 2점: 의미적으로 충분히 동일함

출력 형식:
점수: [0, 1, 또는 2]
이유: [간단한 설명]"""
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "당신은 답변 품질을 평가하는 전문가입니다."},
                {"role": "user", "content": judge_prompt}
            ],
            temperature=0.0,
            max_tokens=200
        )
        result = response.choices[0].message.content.strip()
        
        # 점수 추출
        score_match = re.search(r'점수[:\s]*(\d)', result)
        score = int(score_match.group(1)) if score_match else 0
        score = max(0, min(2, score))  # 0~2 범위로 제한
        
        return score, result
    except Exception as e:
        print(f"✗ Judge 평가 실패: {e}")
        return 0, str(e)


# ============================================================================
# Keyword Hit 평가
# ============================================================================
def extract_keywords(text: str, min_length: int = 2) -> List[str]:
    """텍스트에서 핵심 키워드 추출 (간단한 토큰화)"""
    # 한글, 영문, 숫자만 남기고 토큰화
    text = re.sub(r'[^\w\s가-힣]', ' ', text)
    tokens = text.split()
    
    # 불용어 제거 (간단한 버전)
    stopwords = {'은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '도', '으로', '로', 
                 '입니다', '있습니다', '합니다', '한다', '된다', '이다', '것', '수', '등',
                 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
    
    keywords = [token for token in tokens 
                if len(token) >= min_length and token.lower() not in stopwords]
    
    return list(set(keywords))  # 중복 제거


def calculate_keyword_hit(ground_truth: str, generated_answer: str, min_hits: int = MIN_KEYWORD_HITS) -> Tuple[bool, int, List[str]]:
    """키워드 일치도 평가"""
    gt_keywords = extract_keywords(ground_truth)
    
    if not gt_keywords:
        return True, 0, []  # 키워드가 없으면 통과
    
    matched_keywords = [kw for kw in gt_keywords if kw in generated_answer]
    hit_count = len(matched_keywords)
    is_hit = hit_count >= min_hits
    
    return is_hit, hit_count, matched_keywords


# ============================================================================
# Retrieval Hit Rate 평가
# ============================================================================
def check_retrieval_hit(chunks: List[Dict[str, Any]], ground_truth: str) -> Tuple[bool, List[int]]:
    """검색된 chunk 중에 정답 관련 내용이 있는지 확인"""
    gt_keywords = extract_keywords(ground_truth)
    
    if not gt_keywords:
        return False, []
    
    hit_chunks = []
    for i, chunk in enumerate(chunks):
        chunk_text = chunk['text']
        # 키워드가 3개 이상 포함되거나, 정답 문장의 일부가 포함되면 hit
        matched = sum(1 for kw in gt_keywords if kw in chunk_text)
        if matched >= 3 or ground_truth[:20] in chunk_text:
            hit_chunks.append(i)
    
    return len(hit_chunks) > 0, hit_chunks


# ============================================================================
# QA 데이터 로드
# ============================================================================
def load_qa_data(file_path: str) -> List[Dict[str, Any]]:
    """QA 데이터 로드"""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"QA 파일을 찾을 수 없습니다: {abs_path}")
    
    with open(abs_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"[OK] QA 데이터 로드 완료 (총 {len(data)}개 항목)")
    return data


# ============================================================================
# 평가 실행
# ============================================================================
def evaluate_rag(collection, qa_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """RAG 시스템 전체 평가"""
    results = []
    
    print("\n" + "="*80)
    print("RAG 성능 평가 시작")
    print("="*80 + "\n")
    
    for idx, qa_item in enumerate(tqdm(qa_data, desc="평가 진행 중")):
        question = qa_item['question']
        ground_truth = qa_item['answer']
        
        # 1. Retrieval
        chunks = retrieve_chunks(collection, question, top_k=TOP_K)
        
        # 2. Retrieval Hit Rate
        retrieval_hit, hit_chunk_indices = check_retrieval_hit(chunks, ground_truth)
        
        # 3. LLM 답변 생성
        generated_answer = generate_llm_answer(question, chunks)
        
        # 4. Semantic Similarity
        gt_embedding = get_embedding(ground_truth)
        gen_embedding = get_embedding(generated_answer) if generated_answer else [0] * len(gt_embedding)
        similarity = cosine_similarity(gt_embedding, gen_embedding)
        similarity_hit = similarity >= SIMILARITY_THRESHOLD
        
        # 5. LLM-as-a-judge
        judge_score, judge_reason = judge_semantic_match(ground_truth, generated_answer)
        
        # 6. Keyword Hit
        keyword_hit, keyword_count, matched_keywords = calculate_keyword_hit(ground_truth, generated_answer)
        
        # 결과 저장
        result = {
            'index': idx,
            'question': question,
            'ground_truth': ground_truth,
            'generated_answer': generated_answer,
            'retrieval_hit': bool(retrieval_hit),
            'hit_chunk_indices': hit_chunk_indices,
            'num_retrieved_chunks': len(chunks),
            'semantic_similarity': float(similarity),
            'similarity_hit': bool(similarity_hit),
            'judge_score': int(judge_score),
            'judge_reason': judge_reason,
            'keyword_hit': bool(keyword_hit),
            'keyword_count': int(keyword_count),
            'matched_keywords': matched_keywords,
            'section': qa_item.get('section', ''),
            'source': qa_item.get('source', '')
        }
        results.append(result)
    
    return {'results': results}


# ============================================================================
# 결과 요약 및 출력
# ============================================================================
def summarize_results(evaluation_data: Dict[str, Any]) -> Dict[str, Any]:
    """평가 결과 요약"""
    results = evaluation_data['results']
    total = len(results)
    
    if total == 0:
        return {}
    
    # 집계
    retrieval_hits = sum(1 for r in results if r['retrieval_hit'])
    similarity_hits = sum(1 for r in results if r['similarity_hit'])
    keyword_hits = sum(1 for r in results if r['keyword_hit'])
    
    avg_similarity = np.mean([r['semantic_similarity'] for r in results])
    avg_judge_score = np.mean([r['judge_score'] for r in results])
    
    # 실패 사례 (모든 지표가 실패한 경우)
    failures_raw = [r for r in results if not r['retrieval_hit'] and not r['similarity_hit'] and r['judge_score'] < 1]
    
    # JSON 직렬화를 위해 failures의 모든 값을 Python 기본 타입으로 변환
    failures = []
    for f in failures_raw:
        failure_dict = {}
        for key, value in f.items():
            if isinstance(value, (np.bool_, bool)):
                failure_dict[key] = bool(value)
            elif isinstance(value, (np.integer, np.floating)):
                failure_dict[key] = float(value) if isinstance(value, np.floating) else int(value)
            elif isinstance(value, list):
                failure_dict[key] = [int(x) if isinstance(x, np.integer) else x for x in value]
            else:
                failure_dict[key] = value
        failures.append(failure_dict)
    
    summary = {
        'total_questions': int(total),
        'retrieval_hit_rate': float(retrieval_hits / total),
        'retrieval_hit_count': int(retrieval_hits),
        'semantic_similarity_avg': float(avg_similarity),
        'similarity_hit_rate': float(similarity_hits / total),
        'similarity_hit_count': int(similarity_hits),
        'judge_score_avg': float(avg_judge_score),
        'keyword_hit_rate': float(keyword_hits / total),
        'keyword_hit_count': int(keyword_hits),
        'failure_count': int(len(failures)),
        'failures': failures
    }
    
    return summary


def print_summary(summary: Dict[str, Any]):
    """요약 결과 출력"""
    print("\n" + "="*80)
    print("평가 결과 요약")
    print("="*80)
    print(f"총 질문 수: {summary['total_questions']}")
    print(f"\n[1] Retrieval Hit Rate (가장 중요)")
    print(f"  - Hit: {summary['retrieval_hit_count']}/{summary['total_questions']} ({summary['retrieval_hit_rate']*100:.1f}%)")
    print(f"\n[2] Semantic Similarity")
    print(f"  - 평균 유사도: {summary['semantic_similarity_avg']:.3f}")
    print(f"  - Threshold({SIMILARITY_THRESHOLD}) 이상: {summary['similarity_hit_count']}/{summary['total_questions']} ({summary['similarity_hit_rate']*100:.1f}%)")
    print(f"\n[3] LLM-as-a-judge")
    print(f"  - 평균 점수: {summary['judge_score_avg']:.2f}/2.0")
    print(f"\n[4] Keyword Hit")
    print(f"  - Hit: {summary['keyword_hit_count']}/{summary['total_questions']} ({summary['keyword_hit_rate']*100:.1f}%)")
    print(f"\n[실패 사례]")
    print(f"  - 실패 건수: {summary['failure_count']}")
    
    if summary['failures']:
        print(f"\n주요 실패 사례 (최대 5개):")
        for i, failure in enumerate(summary['failures'][:5], 1):
            print(f"\n  [{i}] 질문: {failure['question'][:60]}...")
            print(f"      정답: {failure['ground_truth'][:60]}...")
            print(f"      생성: {failure['generated_answer'][:60]}...")
            print(f"      Retrieval: {'X' if not failure['retrieval_hit'] else 'O'}, "
                  f"Similarity: {failure['semantic_similarity']:.2f}, "
                  f"Judge: {failure['judge_score']}/2")
    
    print("\n" + "="*80)


# ============================================================================
# 결과 저장
# ============================================================================
def save_results(evaluation_data: Dict[str, Any], summary: Dict[str, Any]):
    """결과를 JSON 및 CSV로 저장"""
    # JSON 저장
    output_data = {
        'summary': summary,
        'detailed_results': evaluation_data['results']
    }
    
    json_path = os.path.abspath(OUTPUT_RESULTS_PATH)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] JSON 결과 저장: {json_path}")
    
    # CSV 저장
    csv_path = os.path.abspath(OUTPUT_CSV_PATH)
    import csv
    
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        if evaluation_data['results']:
            fieldnames = ['index', 'question', 'ground_truth', 'generated_answer', 
                         'retrieval_hit', 'semantic_similarity', 'similarity_hit',
                         'judge_score', 'keyword_hit', 'keyword_count', 'section', 'source']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in evaluation_data['results']:
                row = {k: result.get(k, '') for k in fieldnames}
                writer.writerow(row)
    
    print(f"[OK] CSV 결과 저장: {csv_path}")


# ============================================================================
# 메인 실행
# ============================================================================
def main():
    """메인 실행 함수"""
    print("="*80)
    print("보험 문서 RAG 성능 평가 스크립트")
    print("="*80)
    
    # 1. Chroma DB 로드
    print(f"\n[1] Chroma DB 로드 중...")
    collection = load_chroma_collection(CHROMA_DB_PATH, COLLECTION_NAME)
    
    # 2. QA 데이터 로드
    print(f"\n[2] QA 데이터 로드 중...")
    qa_data = load_qa_data(QA_FILE_PATH)
    
    # 3. 평가 실행
    print(f"\n[3] RAG 평가 실행 중...")
    evaluation_data = evaluate_rag(collection, qa_data)
    
    # 4. 결과 요약
    print(f"\n[4] 결과 요약 중...")
    summary = summarize_results(evaluation_data)
    
    # 5. 결과 출력
    print_summary(summary)
    
    # 6. 결과 저장
    print(f"\n[5] 결과 저장 중...")
    save_results(evaluation_data, summary)
    
    print("\n[OK] 평가 완료!")


if __name__ == "__main__":
    main()
