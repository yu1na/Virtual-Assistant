# Insurance RAG + LLM 평가 가이드

## 📋 개요

`eval_sample_quick.py`는 Insurance RAG 시스템의 성능을 측정하는 실험-친화적 평가 스크립트입니다.

**주요 특징:**
- ✅ 임베딩 모델 변경 가능 (text-embedding-3-small/large, etc.)
- ✅ 검색 전략 실험 (하이브리드 비율, Top-K 등)
- ✅ 자동 실험 추적 (설정별로 결과 저장)
- ✅ 명령줄 인자로 간편하게 설정 변경

## 🚀 사용법

### 기본 실행
```bash
cd /Users/doyeonkim/Documents/GitHub/Virtual-Assistant
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py
```

### 임베딩 모델 변경
```bash
# text-embedding-3-large 사용
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py \
  --embedding-model text-embedding-3-large

# 다른 모델들
# - text-embedding-3-small (기본, 1536D)
# - text-embedding-3-large (3072D, 더 정확하지만 비쌈)
```

### 검색 설정 실험

#### 1. Top-K 값 변경
```bash
# Top-10으로 검색
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py \
  --top-k 10

# Top-3으로 검색
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py \
  --top-k 3
```

#### 2. 하이브리드 검색 비율 (향후 추가 예정)
```bash
# 현재: 1.0 = 벡터 검색만 사용
# 향후: 0.5 = 벡터 50% + 키워드 50%
# 향후: 0.0 = 키워드 검색만 사용
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py \
  --hybrid-ratio 0.5
```

#### 3. 샘플 크기 조정
```bash
# 30개 대신 100개 샘플로 테스트
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py \
  --sample-size 100

# 300개 전체 데이터 평가
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py \
  --sample-size 300
```

### 복합 실험
```bash
# 큰 임베딩 모델 + Top-10 + 100개 샘플
conda run -n dy python backend/app/domain/rag/Insurance/tests/eval_sample_quick.py \
  --embedding-model text-embedding-3-large \
  --top-k 10 \
  --sample-size 100
```

## 📊 결과 해석

결과는 자동으로 설정에 따른 파일명으로 저장됩니다:

```
results/eval_emb_small_hybrid_1.0_topk_5.json
results/eval_emb_large_hybrid_1.0_topk_10.json
...
```

### 저장되는 항목

```json
{
  "config": {
    "embedding_model": "text-embedding-3-small",
    "llm_model": "gpt-4o-mini",
    "top_k": 5,
    "hybrid_ratio": 1.0,
    "sample_size": 30
  },
  "summary": {
    "total": 30,
    "avg_similarity": 0.712,      # 평균 유사도
    "median_similarity": 0.740,   # 중앙값
    "std_similarity": 0.140,      # 표준편차
    "min_similarity": 0.253,      # 최솟값
    "max_similarity": 0.901,      # 최댓값
    "threshold_0.5": 28,          # 0.5 이상 개수
    "threshold_0.6": 23,          # 0.6 이상 개수
    "threshold_0.7": 20           # 0.7 이상 개수
  },
  "results": [...]  # 개별 질문별 상세 결과
}
```

## 📈 벤치마크 비교

### 현재 성능 (기본값: small embedding, Top-5)
- **평균 유사도**: 0.712
- **0.7 이상**: 67%
- **소요 시간**: ~5초/질문

### 개선 가능성
- text-embedding-3-large로 변경 → ~0.02-0.05 향상 예상
- Top-K 증가 → 약간 향상 (but 비용 증가)
- 하이브리드 검색 → 특정 질문에서 개선 가능

## 🔧 향후 확장

### 1. 하이브리드 검색 구현
```python
# 현재 코드 (eval_sample_quick.py line ~105)
if Config.HYBRID_RATIO == 1.0:
    # 순수 벡터 검색
else:
    # BM25 키워드 검색 + 벡터 검색 조합
    # 구현 예정
```

### 2. 재검색 (Reranking) 추가
```bash
# Cohere Rerank 같은 것으로 상위 5개를 재정렬
```

### 3. 프롬프트 튜닝
```python
# generate_answer() 함수에서 시스템 프롬프트 변경
# - 더 자세한 답변
# - 더 간결한 답변
# - 특정 포맷 지정
```

## 🎯 실험 진행 순서 제안

1. **기본 설정 검증** (완료)
   - small embedding, Top-5: 0.712 avg ✅

2. **임베딩 모델 비교**
   ```bash
   # large 모델 테스트
   --embedding-model text-embedding-3-large
   ```

3. **검색 깊이 비교**
   ```bash
   # Top-3, Top-10, Top-20 비교
   --top-k 3/10/20
   ```

4. **샘플 크기로 신뢰도 확보**
   ```bash
   # 전체 300개 평가
   --sample-size 300
   ```

5. **하이브리드 검색 구현 및 테스트**

## 💡 주의사항

### API 비용
- **text-embedding-3-small**: $0.02 per 1M tokens (저비용)
- **text-embedding-3-large**: $0.13 per 1M tokens (고비용)
- 300개 × 5 chunks ≈ $1-2 (small), $5-10 (large)

### 시간
- 30개 샘플: ~2.5분
- 300개 샘플: ~25분

### 결과 비교
```bash
# 모든 실험 결과 비교
ls -lh backend/app/domain/rag/Insurance/tests/results/

# 특정 결과 확인
cat backend/app/domain/rag/Insurance/tests/results/eval_emb_small_hybrid_1.0_topk_5.json | jq '.summary'
```

## 📝 예제 실험

```bash
# 실험 1: 기본값
python eval_sample_quick.py

# 실험 2: 더 강력한 모델
python eval_sample_quick.py --embedding-model text-embedding-3-large --sample-size 100

# 실험 3: 더 넓은 검색
python eval_sample_quick.py --top-k 10 --sample-size 100

# 실험 4: 전체 데이터로 최종 검증
python eval_sample_quick.py --embedding-model text-embedding-3-large --top-k 5 --sample-size 300
```

## 📊 결과 시각화

평가 결과를 자동으로 시각화할 수 있습니다:

```bash
# 시각화 생성
conda run -n dy python backend/app/domain/rag/Insurance/tests/visualize_eval_results.py
```

### 생성되는 차트들

| 파일 | 설명 |
|------|------|
| `01_summary_table.png` | 설정 및 핵심 지표 요약 테이블 |
| `02_similarity_distribution.png` | 유사도 분포 히스토그램 (평균, 중앙값 포함) |
| `03_threshold_comparison.png` | 임계값별 통과율 비교 (≥0.5, 0.6, 0.7, 0.8) |
| `04_performance_trend.png` | 질문별 성능 추이 라인차트 |
| `05_top_bottom_cases.png` | 상위 5개 / 하위 5개 성능 사례 |
| `00_comparison_results.png` | 여러 실험 비교 (실험 2개 이상일 경우) |

### 자동 비교 기능

여러 실험 결과를 생성하면 자동으로 비교 차트를 생성합니다:

```bash
# 실험 1: text-embedding-3-small
python eval_sample_quick.py --sample-size 30

# 실험 2: text-embedding-3-large
python eval_sample_quick.py --embedding-model text-embedding-3-large --sample-size 30

# 실험 3: Top-K=10
python eval_sample_quick.py --top-k 10 --sample-size 30

# 시각화 생성 (자동으로 모든 실험 비교)
python visualize_eval_results.py
```

그러면 `00_comparison_results.png`에서 평균/중앙값/≥0.7 비율을 한눈에 비교할 수 있습니다.

---

**마지막 업데이트**: 2025-12-08
