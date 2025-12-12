"""
평가 자동 실행 스크립트

Usage:
    # 모든 테스트 케이스 실행
    python -m backend.app.domain.brainstorming.evaluation.runner
    
    # 특정 테스트 케이스만 실행
    python -m backend.app.domain.brainstorming.evaluation.runner --case-id tc001
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List
import statistics

# 경로 설정
current_file = Path(__file__).resolve()
module_dir = current_file.parent
project_root = module_dir.parents[4]
sys.path.insert(0, str(project_root))

# 브레인스토밍 모듈 import
from backend.app.domain.brainstorming.session_manager import SessionManager
from backend.app.domain.brainstorming.ephemeral_rag import EphemeralRAG

# ChromaDB 및 OpenAI import
import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI
from dotenv import load_dotenv
import os

# 평가 모듈 import
from .judge import BrainstormingJudge
from .models import SingleRunResult, TestCaseResult, EvaluationSummary, TestCaseInput
from .criteria import WEIGHTS
from .test_cases import ALL_TEST_CASES, get_test_case_by_id

# 트렌드 검색 모듈
import asyncio
from backend.app.domain.brainstorming.search.naver_news import NaverNewsSearcher
from backend.app.domain.brainstorming.search.duckduckgo import DuckDuckGoSearcher
from backend.app.domain.brainstorming.search.naver_datalab import NaverDataLabSearcher

load_dotenv()


class EvaluationRunner:
    """평가 실행기"""
    
    def __init__(self):
        """초기화"""
        self.session_manager = SessionManager()
        self.judge = BrainstormingJudge(model="gpt-5", temperature=1.0)
        
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        
        # Permanent RAG ChromaDB
        brainstorming_path = module_dir.parent
        persist_directory = str(brainstorming_path / "data" / "chroma")
        
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        try:
            self.permanent_collection = self.chroma_client.get_collection(
                name="brainstorming_techniques"
            )
            print("✅ Permanent RAG 컬렉션 로드 완료")
        except Exception as e:
            print(f"⚠️  Permanent RAG 컬렉션 로드 실패: {e}")
            self.permanent_collection = None
        
        # 결과 저장 디렉토리
        self.results_dir = module_dir / "results"
        self.results_dir.mkdir(exist_ok=True)
        
        # 트렌드 검색기 초기화
        try:
            self.trend_searcher = NaverNewsSearcher()
            print("✅ 네이버 트렌드 검색 초기화 완료")
        except Exception as e:
            print(f"⚠️  트렌드 검색 초기화 실패 (기능 비활성화): {e}")
            self.trend_searcher = None
        
        # DuckDuckGo 검색기 초기화
        try:
            self.duckduckgo_searcher = DuckDuckGoSearcher()
            print("✅ DuckDuckGo 트렌드 검색 초기화 완료")
        except Exception as e:
            print(f"⚠️  DuckDuckGo 초기화 실패 (기능 비활성화): {e}")
            self.duckduckgo_searcher = None
        
        # 네이버 데이터랩 검색기 초기화
        try:
            self.datalab_searcher = NaverDataLabSearcher()
            print("✅ 네이버 데이터랩 검색 초기화 완료")
        except Exception as e:
            print(f"⚠️  네이버 데이터랩 초기화 실패 (기능 비활성화): {e}")
            self.datalab_searcher = None
    
    def run_single_test(self, test_case: dict, run_number: int) -> SingleRunResult:
        """
        단일 테스트 실행 (1회)
        
        Args:
            test_case: 테스트 케이스
            run_number: 실행 번호 (1, 2, 3)
        
        Returns:
            SingleRunResult: 실행 결과
        """
        print(f"\n{'='*60}")
        print(f"🔄 실행 {run_number}/3: {test_case['name']}")
        print(f"{'='*60}")
        
        # 1. 세션 생성
        session_id = self.session_manager.create_session()
        print(f"✅ 세션 생성: {session_id}")
        
        session = self.session_manager.get_session(session_id)
        
        try:
            # 2. Q1 목적 입력
            purpose = test_case["q1_purpose"]
            self.session_manager.update_session(session_id, {
                'q1_purpose': purpose
            })
            print(f"✅ Q1 목적 입력 완료")
            
            # 3. Q3 자유연상 입력 + Ephemeral RAG 생성
            associations = test_case["q3_associations"]
            
            ephemeral_rag = EphemeralRAG(session_id=session_id)
            
            ephemeral_rag.add_associations(associations)
            
            self.session_manager.update_session(session_id, {
                'q3_associations': associations,
                'ephemeral_rag_initialized': True
            })
            print(f"✅ Q3 자유연상 입력 + Ephemeral RAG 생성 완료")
            
            # 4. Ephemeral RAG 키워드 추출
            keywords_data = ephemeral_rag.extract_keywords_by_similarity(
                purpose=purpose,
                top_k=5
            )
            extracted_keywords = [kw['keyword'] for kw in keywords_data]
            print(f"✅ Ephemeral RAG 키워드 추출: {extracted_keywords}")
            
            # 5. Permanent RAG 검색
            rag_docs = []
            if self.permanent_collection:
                purpose_embedding = self.openai_client.embeddings.create(
                    input=purpose,
                    model=self.embedding_model
                ).data[0].embedding
                
                results = self.permanent_collection.query(
                    query_embeddings=[purpose_embedding],
                    n_results=3
                )
                
                if results and results.get('documents') and results['documents'][0]:
                    rag_docs = results['documents'][0]
                    print(f"✅ Permanent RAG 검색 완료: {len(rag_docs)}개 문서")
            
            # 6. [NEW] 트렌드 키워드 검색 (네이버 + DuckDuckGo + 데이터랩)
            trend_keywords = []
            
            # 네이버 뉴스
            if self.trend_searcher:
                try:
                    naver_keywords = asyncio.run(
                        self.trend_searcher.extract_trend_keywords(purpose, num_articles=5)
                    )
                    if naver_keywords:
                        print(f"   ✅ 네이버: {len(naver_keywords)}개 발견")
                        trend_keywords.extend(naver_keywords)
                except Exception as e:
                    print(f"⚠️  네이버 트렌드 검색 실패: {e}")
            
            # DuckDuckGo
            if self.duckduckgo_searcher:
                try:
                    ddg_keywords = asyncio.run(
                        self.duckduckgo_searcher.extract_trend_keywords(purpose, num_articles=5)
                    )
                    if ddg_keywords:
                        print(f"   ✅ DuckDuckGo: {len(ddg_keywords)}개 발견")
                        trend_keywords.extend(ddg_keywords)
                except Exception as e:
                    print(f"⚠️  DuckDuckGo 검색 실패: {e}")
            
            # 네이버 데이터랩
            if self.datalab_searcher:
                try:
                    datalab_keywords = asyncio.run(
                        self.datalab_searcher.extract_trend_keywords(purpose)
                    )
                    if datalab_keywords:
                        print(f"   ✅ 네이버 데이터랩: {len(datalab_keywords)}개 발견")
                        trend_keywords.extend(datalab_keywords)
                except Exception as e:
                    print(f"⚠️  네이버 데이터랩 검색 실패: {e}")
            
            # 중복 제거
            trend_keywords = list(dict.fromkeys(trend_keywords))
            print(f"✅ 총 트렌드 키워드: {len(trend_keywords)}개")
            
            # 7. [NEW] 트렌드 키워드 필터링 (사용자 키워드 기준)
            if trend_keywords:
                trend_keywords = ephemeral_rag.filter_trend_keywords(trend_keywords, top_k=10)
                print(f"✅ 필터링 후 트렌드 키워드: {len(trend_keywords)}개")
            
            # 8. 아이디어 생성 (실제 API 로직 복제)
            rag_context = "\n\n".join(rag_docs) if rag_docs else ""
            
            # 트렌드 키워드 문자열 생성
            trend_str = ", ".join(trend_keywords) if trend_keywords else "없음"
            
            prompt = f"""사용자가 "{purpose}"에 대한 아이디어를 원합니다.

【🔴 핵심: 사용자 브레인스토밍 키워드 (비중 80%)】
{', '.join(extracted_keywords)}

※ 위 키워드는 사용자가 직접 떠올린 것입니다. 이 키워드를 중심으로 아이디어를 구성하세요.

【🔵 참고: 최신 트렌드 키워드 (비중 20%)】
{trend_str}

※ 트렌드는 참고만 하세요. 사용자 키워드가 핵심입니다.

【적용 가능한 브레인스토밍 기법】
{rag_context}

---
**🚨 필수 규칙**

1. **반드시 3개 아이디어 생성**

2. **비중 준수**: 사용자 키워드 80% + 트렌드 20%
   - 아이디어의 핵심은 반드시 사용자 키워드에서 나와야 함
   - 트렌드는 시의성 추가용으로만 살짝 활용

3. **할루시네이션 금지**
   ❌ 특정 도구/서비스의 기능을 단정짓기 금지
   ❌ 통계, 비용, 시장규모 지어내기 금지
   ✅ 모르는 건 "확인 필요"로 표시

4. **현실적 실행 가능**: 며칠~몇 주 내 시작 가능한 것만

---
**출력 형식 (반드시 이 형식으로 3개 작성)**:

---
아이디어 제목: [제목]

주제: [어떤 문제/니즈를 해결하는지]

실행 방향: [무엇을 할지 - 구체적 도구나 수치 단정 금지, 방향성만]

확인 필요 사항: [실행 전 조사해봐야 할 것들]

기대효과: [예상 결과 - 숫자 단정 금지]

적용된 기법: [기법명]
---

**⚠️ 반드시 위 형식으로 3개 모두 작성하세요!**"""
            
            idea_response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 유능한 기획자입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            ideas_text = idea_response.choices[0].message.content.strip()
            print(f"✅ 아이디어 생성 완료")
            
            # 9. 아이디어 파싱 (새 형식)
            ideas = []
            current_idea = {}
            current_field = None
            
            for line in ideas_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('---'):
                    if current_idea and current_idea.get('title'):
                        ideas.append(current_idea)
                    current_idea = {}
                    current_field = None
                elif line.startswith('아이디어 제목:') or line.startswith('제목:'):
                    current_idea['title'] = line.split(':', 1)[1].strip()
                    current_field = None
                elif line.startswith('주제:'):
                    current_idea['subject'] = line.split(':', 1)[1].strip()
                    current_field = 'subject'
                elif line.startswith('실행 방향:'):
                    current_idea['direction'] = line.split(':', 1)[1].strip()
                    current_field = 'direction'
                elif line.startswith('확인 필요 사항:') or line.startswith('확인 필요:'):
                    current_idea['check_needed'] = line.split(':', 1)[1].strip()
                    current_field = 'check_needed'
                elif line.startswith('기대효과:') or line.startswith('기대 효과:'):
                    current_idea['expected_effect'] = line.split(':', 1)[1].strip()
                    current_field = 'expected_effect'
                elif line.startswith('적용된 기법:') or line.startswith('기법:'):
                    current_idea['technique'] = line.split(':', 1)[1].strip()
                    current_field = None
                # 기존 형식 호환
                elif line.startswith('- 설명:') or line.startswith('설명:'):
                    current_idea['description'] = line.split(':', 1)[1].strip()
                    current_field = 'description'
                elif line.startswith('아이디어') and ':' in line:
                    if current_idea and current_idea.get('title'):
                        ideas.append(current_idea)
                    title = line.split(':', 1)[1].strip()
                    current_idea = {'title': title}
                    current_field = None
                elif current_field and line:
                    if current_field in current_idea:
                        current_idea[current_field] += ' ' + line
                    else:
                        current_idea[current_field] = line
            
            if current_idea and current_idea.get('title'):
                ideas.append(current_idea)
            
            # 10. SWOT 분석 추가
            for idea in ideas:
                idea_content = f"""
제목: {idea.get('title', '')}
주제: {idea.get('subject', idea.get('description', ''))}
실행 방향: {idea.get('direction', '')}
"""
                swot_prompt = f"""**역할**: 현실적인 기획자

**아이디어**: {idea_content}

**요구사항**:
1. 이 아이디어에 대한 **SWOT 분석** 수행
2. **현실적 관점**에서 분석 (사용자의 상황: 개인/소규모 팀/회사)
3. 각 항목을 **1-2줄**로 간결하게 작성
4. **허위 데이터 절대 금지** (모르면 "조사 필요")

**출력 형식**:
Strengths (강점):
- [강점 1]
- [강점 2]

Weaknesses (약점):
- [약점 1]
- [약점 2]

Opportunities (기회):
- [기회 1]
- [기회 2]

Threats (위협):
- [위협 1]
- [위협 2]
"""
                
                swot_response = self.openai_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": "당신은 현실적인 기획자입니다."},
                        {"role": "user", "content": swot_prompt}
                    ],
                    temperature=0.6,
                    max_tokens=500
                )
                
                idea['analysis'] = swot_response.choices[0].message.content.strip()
            
            print(f"✅ SWOT 분석 완료: {len(ideas)}개 아이디어")
            
            # 11. 최종 텍스트 포맷
            final_ideas_text = ""
            for i, idea in enumerate(ideas, 1):
                final_ideas_text += f"📌 아이디어 {i}: {idea.get('title', '')}\n\n"
                if idea.get('subject'):
                    final_ideas_text += f"주제: {idea.get('subject')}\n"
                if idea.get('direction'):
                    final_ideas_text += f"실행 방향: {idea.get('direction')}\n"
                if idea.get('check_needed'):
                    final_ideas_text += f"확인 필요: {idea.get('check_needed')}\n"
                if idea.get('expected_effect'):
                    final_ideas_text += f"기대효과: {idea.get('expected_effect')}\n"
                if idea.get('description'):
                    final_ideas_text += f"설명: {idea.get('description')}\n"
                final_ideas_text += f"\n📊 SWOT 분석:\n\n{idea.get('analysis', '')}\n\n"
            
            # 12. Judge 평가
            print(f"🔍 Judge 평가 중... (GPT-5)")
            scores = self.judge.evaluate(
                question=purpose,
                answer=final_ideas_text,
                permanent_rag_docs=rag_docs,
                ephemeral_keywords=extracted_keywords
            )
            
            weighted_total = scores.weighted_average(WEIGHTS)
            
            print(f"✅ 평가 완료:")
            print(f"   - rag_utilization (RAG 활용도): {scores.rag_utilization}/10")
            print(f"   - completeness (답변 완성도): {scores.completeness}/10")
            print(f"   - relevance (질문-답변 연관도): {scores.relevance}/10")
            print(f"   - creativity (창의성): {scores.creativity}/10")
            print(f"   - practicality (실용성): {scores.practicality}/10")
            print(f"   - weighted_total (가중 평균): {weighted_total}/10")
            
            # 13. 결과 생성
            result = SingleRunResult(
                run_number=run_number,
                session_id=session_id,
                ideas_text=final_ideas_text,
                ideas_count=len(ideas),
                permanent_rag_docs=rag_docs,
                ephemeral_keywords=extracted_keywords,
                scores=scores,
                weighted_total=weighted_total
            )
            
            return result
            
        finally:
            # 14. 세션 정리
            self.session_manager.delete_session(session_id)
            print(f"✅ 세션 정리 완료")
    
    def run_test_case(self, test_case: dict) -> TestCaseResult:
        """
        테스트 케이스 실행 (3회 반복)
        
        Args:
            test_case: 테스트 케이스
        
        Returns:
            TestCaseResult: 테스트 케이스 전체 결과
        """
        print(f"\n{'#'*60}")
        print(f"🚀 테스트 케이스 시작: {test_case['name']} ({test_case['id']})")
        print(f"{'#'*60}")
        
        runs = []
        
        # 3회 실행
        for i in range(1, 4):
            run_result = self.run_single_test(test_case, i)
            runs.append(run_result)
        
        # 평균 계산
        avg_rag = sum(r.scores.rag_utilization for r in runs) / 3
        avg_comp = sum(r.scores.completeness for r in runs) / 3
        avg_rel = sum(r.scores.relevance for r in runs) / 3
        avg_cre = sum(r.scores.creativity for r in runs) / 3
        avg_prac = sum(r.scores.practicality for r in runs) / 3
        avg_weighted = sum(r.weighted_total for r in runs) / 3
        
        average_scores = {
            "rag_utilization": round(avg_rag, 2),
            "completeness": round(avg_comp, 2),
            "relevance": round(avg_rel, 2),
            "creativity": round(avg_cre, 2),
            "practicality": round(avg_prac, 2),
        }
        
        # 표준편차 계산
        weighted_scores = [r.weighted_total for r in runs]
        std_dev = round(statistics.stdev(weighted_scores) if len(weighted_scores) > 1 else 0.0, 2)
        
        result = TestCaseResult(
            test_case_id=test_case["id"],
            test_case_name=test_case["name"],
            runs=runs,
            average_scores=average_scores,
            average_weighted_total=round(avg_weighted, 2),
            std_deviation=std_dev
        )
        
        # 한글 레이블 매핑
        label_map = {
            "rag_utilization": "RAG 활용도",
            "completeness": "답변 완성도",
            "relevance": "질문-답변 연관도",
            "creativity": "창의성",
            "practicality": "실용성"
        }
        
        print(f"\n{'='*60}")
        print(f"📊 테스트 케이스 완료: {test_case['name']}")
        print(f"{'='*60}")
        print(f"평균 점수:")
        for key, value in average_scores.items():
            korean_label = label_map.get(key, key)
            print(f"  - {key} ({korean_label}): {value}/10")
        print(f"weighted_total (가중 평균): {result.average_weighted_total}/10")
        print(f"std_deviation (표준편차): {std_dev} (낮을수록 일관성 높음)")
        
        return result
    
    def save_result(self, result: TestCaseResult):
        """결과 JSON 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{result.test_case_id}_result.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        
        print(f"✅ 결과 저장: {filepath}")
    
    def run_all(self):
        """모든 테스트 케이스 실행"""
        print(f"\n{'#'*60}")
        print(f"🎯 전체 평가 시작")
        print(f"{'#'*60}")
        print(f"테스트 케이스: {len(ALL_TEST_CASES)}개")
        
        all_results = []
        
        for test_case in ALL_TEST_CASES:
            result = self.run_test_case(test_case)
            self.save_result(result)
            all_results.append(result)
        
        # 전체 요약
        overall_avg = sum(r.average_weighted_total for r in all_results) / len(all_results)
        
        summary = EvaluationSummary(
            test_cases=all_results,
            overall_average=round(overall_avg, 2),
            model_info={
                "worker_model": self.llm_model,
                "judge_model": self.judge.model,
                "embedding_model": self.embedding_model
            }
        )
        
        # 요약 저장
        summary_filename = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary_filepath = self.results_dir / summary_filename
        
        with open(summary_filepath, 'w', encoding='utf-8') as f:
            json.dump(summary.model_dump(), f, ensure_ascii=False, indent=2)
        
        print(f"\n{'#'*60}")
        print(f"✅ 전체 평가 완료!")
        print(f"{'#'*60}")
        print(f"overall_average (전체 평균 점수): {overall_avg}/10")
        print(f"summary_file (요약 파일): {summary_filepath}")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="브레인스토밍 평가 자동 실행")
    parser.add_argument(
        "--case-id",
        type=str,
        help="특정 테스트 케이스 ID (예: tc001). 생략 시 전체 실행"
    )
    
    args = parser.parse_args()
    
    runner = EvaluationRunner()
    
    if args.case_id:
        # 특정 케이스만 실행
        test_case = get_test_case_by_id(args.case_id)
        result = runner.run_test_case(test_case)
        runner.save_result(result)
    else:
        # 전체 실행
        runner.run_all()


if __name__ == "__main__":
    main()

