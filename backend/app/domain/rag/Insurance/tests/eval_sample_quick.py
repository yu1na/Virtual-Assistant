#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Insurance RAG + LLM 평가 (실험 가능한 버전)
임베딩 모델, retriever 하이브리드 비율 등을 쉽게 변경 가능
"""

import os
import json
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any

env_path = Path('/Users/doyeonkim/Documents/GitHub/Virtual-Assistant/.env')
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.startswith('OPENAI_API_KEY='):
                os.environ['OPENAI_API_KEY'] = line.split('=')[1].strip().strip('"\'')
                break

import chromadb
from openai import OpenAI
import numpy as np
from tqdm import tqdm

# ===== 설정값 (CLI로도 오버라이드 가능) =====
class Config:
    # 경로
    CHROMA_DB_PATH = 'backend/app/domain/rag/Insurance/chroma_db'
    COLLECTION_NAME = 'insurance_manual'
    QA_FILE_PATH = 'backend/app/domain/rag/Insurance/tests/qa_filtered_300.json'
    
    # 임베딩/LLM 모델
    EMBEDDING_MODEL = "text-embedding-3-small"  # 실험할 때: text-embedding-3-large 등으로 변경
    LLM_MODEL = "gpt-4o-mini"
    
    # 검색 설정
    TOP_K = 5
    HYBRID_RATIO = 1.0  # 1.0 = 순수 벡터, 0.0 = 순수 키워드, 0.5 = 하이브리드 50/50
    
    # 평가 설정
    SAMPLE_SIZE = 30
    RANDOM_SEED = 42
    
    @classmethod
    def get_output_path(cls):
        """실험 설정에 따른 출력 경로 자동 생성"""
        exp_name = f"emb_{cls.EMBEDDING_MODEL.split('-')[-1]}_hybrid_{cls.HYBRID_RATIO}_topk_{cls.TOP_K}"
        return f'backend/app/domain/rag/Insurance/tests/results/eval_{exp_name}.json'
    
    @classmethod
    def update_from_args(cls, args):
        """CLI 인자로 설정 업데이트"""
        if args.embedding_model:
            cls.EMBEDDING_MODEL = args.embedding_model
        if args.hybrid_ratio is not None:
            cls.HYBRID_RATIO = args.hybrid_ratio
        if args.top_k:
            cls.TOP_K = args.top_k
        if args.sample_size:
            cls.SAMPLE_SIZE = args.sample_size

def parse_args():
    parser = argparse.ArgumentParser(description='Insurance RAG + LLM 평가')
    parser.add_argument('--embedding-model', help='임베딩 모델 (기본: text-embedding-3-small)')
    parser.add_argument('--hybrid-ratio', type=float, help='하이브리드 비율 (0.0~1.0, 기본: 1.0)')
    parser.add_argument('--top-k', type=int, help='Top-K 검색 결과 수 (기본: 5)')
    parser.add_argument('--sample-size', type=int, help='평가 샘플 수 (기본: 30)')
    return parser.parse_args()

print("[1] 데이터 로드...")
args = parse_args()
Config.update_from_args(args)

print(f"⚙️  실험 설정:")
print(f"  임베딩 모델: {Config.EMBEDDING_MODEL}")
print(f"  하이브리드 비율: {Config.HYBRID_RATIO}")
print(f"  Top-K: {Config.TOP_K}")
print(f"  샘플 수: {Config.SAMPLE_SIZE}")
print()

client = chromadb.PersistentClient(path=Config.CHROMA_DB_PATH)
collection = client.get_collection(Config.COLLECTION_NAME)

with open(Config.QA_FILE_PATH, 'r', encoding='utf-8') as f:
    all_qa_data = json.load(f)

# 샘플링
random.seed(Config.RANDOM_SEED)
qa_data = random.sample(all_qa_data, min(Config.SAMPLE_SIZE, len(all_qa_data)))
print(f"✅ {len(all_qa_data)}개 중 {Config.SAMPLE_SIZE}개 샘플링")

openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

def get_embedding(text: str) -> List[float]:
    """텍스트 임베딩 생성"""
    response = openai_client.embeddings.create(
        input=text[:8000],
        model=Config.EMBEDDING_MODEL
    )
    return response.data[0].embedding

def retrieve_context(question: str, top_k: int = None) -> List[str]:
    """ChromaDB에서 관련 청크 검색 (하이브리드 지원)"""
    if top_k is None:
        top_k = Config.TOP_K
    
    query_emb = get_embedding(question)
    
    # 하이브리드 검색: 벡터 + 키워드
    # 현재는 벡터만 사용 (HYBRID_RATIO=1.0)
    # 추후 BM25 등 키워드 검색 추가 가능
    if Config.HYBRID_RATIO == 1.0:
        # 순수 벡터 검색
        search_results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k
        )
    else:
        # 하이브리드 검색 (구현 예정)
        # bm25_results = keyword_search(question, alpha=1-HYBRID_RATIO)
        # vector_results = vector_search(query_emb, alpha=HYBRID_RATIO)
        # results = merge_results(bm25_results, vector_results)
        search_results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k
        )
    
    return search_results['documents'][0] if search_results['documents'] else []

def generate_answer(question: str, context_chunks: List[str]) -> str:
    """LLM으로 답변 생성"""
    context = "\n\n".join([f"[문서 {i+1}]\n{chunk[:300]}" for i, chunk in enumerate(context_chunks)])
    
    prompt = f"""당신은 보험 전문가입니다. 아래 문서를 참고하여 질문에 정확하게 답변하세요.

[참고 문서]
{context}

[질문]
{question}

[답변]"""
    
    try:
        response = openai_client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": "당신은 보험 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[오류: {str(e)[:30]}]"

def calc_similarity(text1: str, text2: str) -> float:
    """코사인 유사도 계산"""
    try:
        emb1 = np.array(get_embedding(text1))
        emb2 = np.array(get_embedding(text2))
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(similarity)
    except:
        return 0.0

print(f"\n[2] 평가 실행 중... ({Config.SAMPLE_SIZE}개 샘플)")
results = []

for qa_item in tqdm(qa_data, desc="평가"):
    question = qa_item.get('question', '')
    ground_truth = qa_item.get('answer', '')
    section = qa_item.get('section', '')
    
    if not question or not ground_truth:
        continue
    
    try:
        context = retrieve_context(question)
        answer = generate_answer(question, context)
        
        if "[오류" in answer:
            continue
        
        similarity = calc_similarity(answer, ground_truth)
        
        results.append({
            'question': question[:100],
            'section': section[:60],
            'ground_truth': ground_truth[:150],
            'generated': answer[:150],
            'similarity': similarity
        })
    except:
        continue

print(f"\n[3] 통계...")
sims = [r['similarity'] for r in results]

print("\n" + "="*70)
print(f"📊 RAG + LLM 평가 결과 ({Config.SAMPLE_SIZE} 샘플)")
print("="*70)
print(f"\n실험 설정:")
print(f"  임베딩: {Config.EMBEDDING_MODEL}")
print(f"  하이브리드: {Config.HYBRID_RATIO}")
print(f"  Top-K: {Config.TOP_K}")
print(f"\n성과:")
print(f"  평균 유사도: {np.mean(sims):.3f}")
print(f"  중앙값: {np.median(sims):.3f}")
print(f"  범위: {np.min(sims):.3f} ~ {np.max(sims):.3f}")

print(f"\n유사도 분포:")
print(f"  >= 0.5: {sum(1 for s in sims if s >= 0.5)}/{len(results)} ({sum(1 for s in sims if s >= 0.5)/len(results)*100:.0f}%)")
print(f"  >= 0.6: {sum(1 for s in sims if s >= 0.6)}/{len(results)} ({sum(1 for s in sims if s >= 0.6)/len(results)*100:.0f}%)")
print(f"  >= 0.7: {sum(1 for s in sims if s >= 0.7)}/{len(results)} ({sum(1 for s in sims if s >= 0.7)/len(results)*100:.0f}%)")

print(f"\n샘플 결과 (상위 5개):")
sorted_results = sorted(results, key=lambda x: x['similarity'], reverse=True)
for i, r in enumerate(sorted_results[:5], 1):
    print(f"\n[{i}] 유사도: {r['similarity']:.3f}")
    print(f"  Q: {r['question']}")
    print(f"  정답: {r['ground_truth'][:100]}")
    print(f"  생성: {r['generated'][:100]}")

# 저장
output_path = Config.get_output_path()
Path(output_path).parent.mkdir(parents=True, exist_ok=True)

output = {
    'config': {
        'embedding_model': Config.EMBEDDING_MODEL,
        'llm_model': Config.LLM_MODEL,
        'top_k': Config.TOP_K,
        'hybrid_ratio': Config.HYBRID_RATIO,
        'sample_size': Config.SAMPLE_SIZE,
    },
    'summary': {
        'total': len(results),
        'avg_similarity': float(np.mean(sims)),
        'median_similarity': float(np.median(sims)),
        'std_similarity': float(np.std(sims)),
        'min_similarity': float(np.min(sims)),
        'max_similarity': float(np.max(sims)),
        'threshold_0.5': sum(1 for s in sims if s >= 0.5),
        'threshold_0.6': sum(1 for s in sims if s >= 0.6),
        'threshold_0.7': sum(1 for s in sims if s >= 0.7),
    },
    'results': results
}

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n💾 저장: {output_path}")
print("✅ 완료!")
