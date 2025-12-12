import os
import pandas as pd
import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

class RAGEvaluator:
    def __init__(self, model_name: str = "gpt-4o"):
        """
        RAG 평가를 위한 초기화
        
        Args:
            model_name: 평가에 사용할 LLM 모델명 (기본값: gpt-4o)
        """
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.output_parser = JsonOutputParser()
        
        # Ground Truth 데이터 로드 (실시간 조회를 위해)
        # 현재 파일 위치: backend/app/domain/rag/HR/evaluator.py
        # 목표: backend/data/HR_RAG/HR_RAG_GTA/ground_truth_annotations.xlsx
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # backend/app/domain/rag/HR -> backend/app/domain/rag -> backend/app/domain -> backend/app -> backend
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))
        
        # 만약 project_root가 'backend'로 끝난다면 (즉, backend 폴더 내부에서 실행 중이라면)
        # 하지만 구조상 Virtual-Assistant/backend/... 이므로 5번 올라가면 backend 폴더가 나옴.
        # 6번 올라가야 Virtual-Assistant 루트임.
        
        # 안전하게 backend 폴더를 찾아서 그 상위를 root로 잡거나, backend 폴더 기준으로 경로 설정
        # 여기서는 backend 폴더를 기준으로 설정
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
        
        self.gt_file_path = os.path.join(backend_dir, "data", "HR_RAG", "HR_RAG_GTA", "ground_truth_annotations.xlsx")
        self.gt_df = None
        
        print(f"[DEBUG] Ground Truth Path: {self.gt_file_path}")
        self._load_gt_data()

    def _load_gt_data(self):
        """Ground Truth 데이터를 메모리에 로드합니다."""
        if os.path.exists(self.gt_file_path):
            try:
                self.gt_df = pd.read_excel(self.gt_file_path)
                print(f"[DEBUG] Ground Truth Loaded: {len(self.gt_df)} rows")
                # 컬럼명 공백 제거 및 소문자 변환 등으로 정규화할 수도 있음
            except Exception as e:
                print(f"Ground Truth 로드 실패: {e}")
                self.gt_df = pd.DataFrame()
        else:
            print(f"[DEBUG] Ground Truth File Not Found at: {self.gt_file_path}")
            self.gt_df = pd.DataFrame()

    def lookup_ground_truth(self, query: str) -> str:
        """
        질문과 일치하는 Ground Truth를 찾습니다.
        정확히 일치하는 질문이 있을 경우에만 반환합니다.
        """
        if self.gt_df is None or self.gt_df.empty:
            # 데이터가 비어있다면 다시 로드 시도 (초기화 시 실패했을 수 있음)
            print("[DEBUG] Ground Truth DataFrame is empty. Retrying load...")
            self._load_gt_data()
            
            if self.gt_df is None or self.gt_df.empty:
                return None
            
        # 질문 컬럼 확인
        if "question" not in self.gt_df.columns or "ground_truth" not in self.gt_df.columns:
            return None
            
        # 정확한 매칭 (공백 제거 후 소문자 비교)
        query_norm = query.strip().lower()
        
        # 질문 컬럼도 정규화하여 비교
        # 1. 문자열로 변환
        # 2. 양쪽 공백 제거
        # 3. 소문자 변환
        questions_norm = self.gt_df["question"].astype(str).str.strip().str.lower()
        
        match = self.gt_df[questions_norm == query_norm]
        
        if not match.empty:
            return str(match.iloc[0]["ground_truth"])
        
        return None

    def load_data(self, file_path: str) -> pd.DataFrame:
        """
        Ground Truth 엑셀 파일을 로드합니다.
        
        Args:
            file_path: 엑셀 파일 경로
            
        Returns:
            pd.DataFrame: 로드된 데이터
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        return pd.read_excel(file_path)

    def _get_evaluation_prompt(self, metric_name: str, definition: str, scoring_guide: str) -> ChatPromptTemplate:
        """
        평가 프롬프트를 생성합니다.
        """
        system_template = """당신은 공정한 채점관입니다. 
다음 [질문], [문서], [답변], [Ground Truth] 등을 보고 '{metric_name}'을 평가하세요.

### 평가 지표: {metric_name}
{definition}

### 채점 가이드라인
{scoring_guide}

### 출력 형식
반드시 다음 JSON 포맷으로 응답하세요:
{{
  "score": 점수 (1, 2, 3, 4, 5 중 하나),
  "reason": "채점 이유 설명"
}}
"""
        return ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("user", """
[질문]
{question}

[문서 (Context)]
{context}

[AI 답변]
{answer}

[Ground Truth]
{ground_truth}
""")
        ])

    def evaluate_faithfulness(self, question: str, context: str, answer: str) -> Dict[str, Any]:
        """
        1) 정확성 (Faithfulness) 평가
        """
        definition = "답변이 검색된 문서(Context)에 근거하고 있는지 평가."
        scoring_guide = """
   - **5점:** 모든 내용이 문서에 명확한 근거가 있으며, 왜곡이 없음.
   - **4점:** 핵심은 정확하나, 문서에 없는 사소한 부연 설명이 한 문장 정도 포함됨.
   - **3점:** 절반 이상의 내용이 근거가 있으나, 일부 내용이 문서에 없거나 모호함.
   - **2점:** 근거가 있는 내용이 일부 있지만, 절반 이상이 문서에 없거나 부정확함.
   - **1점:** 문서에 없는 내용을 지어내거나(Hallucination), 문서와 모순됨.
"""
        prompt = self._get_evaluation_prompt("정확성 (Faithfulness)", definition, scoring_guide)
        chain = prompt | self.llm | self.output_parser
        
        try:
            return chain.invoke({
                "metric_name": "정확성 (Faithfulness)",
                "definition": definition,
                "scoring_guide": scoring_guide,
                "question": question,
                "context": context,
                "answer": answer,
                "ground_truth": "(참고용 - 이 지표에서는 주로 Context와 Answer의 관계를 봅니다)"
            })
        except Exception as e:
            return {"score": 0, "reason": f"Error: {str(e)}"}

    def evaluate_context_precision(self, question: str, context: str, ground_truth: str) -> Dict[str, Any]:
        """
        2) 컨텍스트 정밀도 (Context Precision) 평가
        """
        definition = "검색된 문서(Context) 중 실제 정답에 필요한 정보가 얼마나 상위에 있는지 평가."
        scoring_guide = """
   - **5점:** 최상위(1~2번) 문서에 정답이 완벽하게 포함됨.
   - **4점:** 최상위 문서에 정답이 있지만, 일부 정보는 3~4번째 문서에서 찾아야 함.
   - **3점:** 정보가 있긴 하나 하위 순위(3번째 이후)에 있거나, 여러 문서에 흩어져 있음.
   - **2점:** 관련 키워드가 포함된 문서는 있지만, 정답을 도출하기엔 정보가 많이 부족함.
   - **1점:** 검색된 문서들에 정답을 도출할 정보가 아예 없음.
"""
        prompt = self._get_evaluation_prompt("컨텍스트 정밀도 (Context Precision)", definition, scoring_guide)
        chain = prompt | self.llm | self.output_parser
        
        try:
            return chain.invoke({
                "metric_name": "컨텍스트 정밀도 (Context Precision)",
                "definition": definition,
                "scoring_guide": scoring_guide,
                "question": question,
                "context": context,
                "answer": "(평가 대상 아님)",
                "ground_truth": ground_truth
            })
        except Exception as e:
            return {"score": 0, "reason": f"Error: {str(e)}"}

    def evaluate_completeness(self, question: str, answer: str) -> Dict[str, Any]:
        """
        3) 완전성 (Completeness) 평가
        """
        definition = "질문의 모든 요구사항을 빠짐없이 다루었는지 평가."
        scoring_guide = """
- **5점:** 질문의 모든 요소(조건, 기간, 대상 등)를 완벽하게 답변함.
- **4점:** 질문에 대해 모두 답변은 하였으나 한가지 사항을 제외한 나머지 사항은 설명이 불충분함.
- **3점:** 질문에 대해 모든 답변을 하였으나 전체적으로 설명이 불충분함.
- **2점:** 질문의 한가지 사항에 대해서만 답변함.
- **1점:** 질문의 핵심을 놓치거나 동문서답함.
"""
        prompt = self._get_evaluation_prompt("완전성 (Completeness)", definition, scoring_guide)
        chain = prompt | self.llm | self.output_parser
        
        try:
            return chain.invoke({
                "metric_name": "완전성 (Completeness)",
                "definition": definition,
                "scoring_guide": scoring_guide,
                "question": question,
                "context": "(참고용)",
                "answer": answer,
                "ground_truth": "(참고용)"
            })
        except Exception as e:
            return {"score": 0, "reason": f"Error: {str(e)}"}

    def evaluate_answer_relevancy(self, question: str, answer: str) -> Dict[str, Any]:
        """
        4) 연관성 (Answer Relevancy) 평가
        """
        definition = "답변이 질문의 의도에 맞고 쓸데없는 정보가 없는지 평가."
        scoring_guide = """
   - **5점:** 질문의 의도를 정확히 파악하고 군더더기 없이 답변함.
   - **4점:** 의도에 맞지만, 불필요한 서론이나 사족이 약간 있음.
   - **3점:** 질문의 의도는 파악했으나, 핵심 정보가 누락되어 답변이 불완전함.
   - **2점:** 질문의 핵심에서 벗어나 주변적인 이야기만 함.
   - **1점:** 질문과 전혀 상관없는 주제를 말함.
"""
        prompt = self._get_evaluation_prompt("연관성 (Answer Relevancy)", definition, scoring_guide)
        chain = prompt | self.llm | self.output_parser
        
        try:
            return chain.invoke({
                "metric_name": "연관성 (Answer Relevancy)",
                "definition": definition,
                "scoring_guide": scoring_guide,
                "question": question,
                "context": "(참고용)",
                "answer": answer,
                "ground_truth": "N/A (Not used for Answer Relevancy)"
            })
        except Exception as e:
            return {"score": 0, "reason": f"Error: {str(e)}"}

    def evaluate_answer_correctness(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        """
        5) 정답 일치도 (Answer Correctness) 평가
        """
        definition = "[Ground Truth]와 [AI Answer]의 의미가 일치하는지 평가."
        scoring_guide = """
   - **5점:** 의미와 핵심 디테일(수치, 날짜 등)이 완벽하게 일치함.
   - **4점:** 의미는 일치하나, 단어 선택이나 표현 방식이 약간 다름 (틀린 건 아님).
   - **3점:** 전체적인 결론은 같으나, 세부 디테일(날짜, 금액 등)이 일부 틀림.
   - **2점:** 일부 맞는 내용도 있으나, 핵심 결론이 [Ground Truth]와 다름.
   - **1점:** 의미가 완전히 다르거나 틀린 정보를 포함함.
"""
        prompt = self._get_evaluation_prompt("정답 일치도 (Answer Correctness)", definition, scoring_guide)
        chain = prompt | self.llm | self.output_parser
        
        try:
            return chain.invoke({
                "metric_name": "정답 일치도 (Answer Correctness)",
                "definition": definition,
                "scoring_guide": scoring_guide,
                "question": question,
                "context": "(참고용)",
                "answer": answer,
                "ground_truth": ground_truth
            })
        except Exception as e:
            return {"score": 0, "reason": f"Error: {str(e)}"}

    def evaluate_single(self, question: str, answer: str, context: str, ground_truth: str = None) -> Dict[str, Any]:
        """
        단일 질문에 대한 평가를 수행합니다.
        Ground Truth가 없으면 관련 지표(Context Precision, Answer Correctness)는 스킵하거나 N/A 처리합니다.
        """
        result = {
            "question": question,
            "answer": answer,
            "context": context,
            "ground_truth": ground_truth
        }
        
        # 1. Faithfulness (Ground Truth 불필요)
        faithfulness = self.evaluate_faithfulness(question, context, answer)
        result.update({
            "faithfulness_score": faithfulness.get("score"),
            "faithfulness_reason": faithfulness.get("reason")
        })
        
        # 3. Completeness (Ground Truth 불필요)
        completeness = self.evaluate_completeness(question, answer)
        result.update({
            "completeness_score": completeness.get("score"),
            "completeness_reason": completeness.get("reason")
        })
        
        # 4. Answer Relevancy (Ground Truth 불필요)
        answer_relevancy = self.evaluate_answer_relevancy(question, answer)
        result.update({
            "answer_relevancy_score": answer_relevancy.get("score"),
            "answer_relevancy_reason": answer_relevancy.get("reason")
        })
        
        if ground_truth:
            # 2. Context Precision (Ground Truth 필요)
            context_precision = self.evaluate_context_precision(question, context, ground_truth)
            result.update({
                "context_precision_score": context_precision.get("score"),
                "context_precision_reason": context_precision.get("reason")
            })
            
            # 5. Answer Correctness (Ground Truth 필요)
            answer_correctness = self.evaluate_answer_correctness(question, answer, ground_truth)
            result.update({
                "answer_correctness_score": answer_correctness.get("score"),
                "answer_correctness_reason": answer_correctness.get("reason")
            })
        else:
            # Ground Truth가 없는 경우 N/A 처리
            result.update({
                "context_precision_score": "N/A",
                "context_precision_reason": "Ground Truth 없음",
                "answer_correctness_score": "N/A",
                "answer_correctness_reason": "Ground Truth 없음"
            })
            
        return result

    def run_evaluation(self, input_file: str, output_file: str):
        """
        전체 평가 프로세스를 실행합니다.
        """
        print(f"Loading data from {input_file}...")
        try:
            df = self.load_data(input_file)
        except FileNotFoundError:
            print(f"❌ 입력 파일을 찾을 수 없습니다: {input_file}")
            print("엑셀 파일을 해당 경로에 위치시킨 후 다시 실행해주세요.")
            df = pd.DataFrame()
        
        # 필수 컬럼 확인
        required_columns = ["question", "answer", "retrieved_docs", "ground_truth"]
        for col in required_columns:
            if col not in df.columns:
                print(f"Warning: '{col}' 컬럼이 없습니다. 빈 값으로 채웁니다.")
                df[col] = ""

        results = []
        
        print("Starting evaluation...")
        for index, row in df.iterrows():
            print(f"Evaluating row {index + 1}/{len(df)}...")
            
            question = str(row.get("question", ""))
            answer = str(row.get("answer", ""))
            context = str(row.get("retrieved_docs", ""))
            ground_truth = str(row.get("ground_truth", ""))
            
            # 단일 평가 실행
            row_result = self.evaluate_single(question, answer, context, ground_truth)
            
            # 결과 출력
            print(f"  - 정확성: {row_result.get('faithfulness_score')}점")
            if ground_truth:
                print(f"  - 정밀도: {row_result.get('context_precision_score')}점")
            print(f"  - 완전성: {row_result.get('completeness_score')}점")
            print(f"  - 연관성: {row_result.get('answer_relevancy_score')}점")
            if ground_truth:
                print(f"  - 일치도: {row_result.get('answer_correctness_score')}점")
            print("-" * 50)
            
            # 원본 데이터와 병합 (이미 evaluate_single에서 기본 정보는 포함하지만, 원본의 다른 컬럼 유지를 위해)
            full_result = row.to_dict()
            full_result.update(row_result)
            results.append(full_result)

        # 결과 저장
        result_df = pd.DataFrame(results)
        
        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        result_df.to_json(output_file, orient='records', force_ascii=False, indent=4)
        print(f"Evaluation completed. Results saved to {output_file}")

if __name__ == "__main__":
    # 사용 예시
    evaluator = RAGEvaluator()
    
    input_path = "backend/data/HR_RAG/HR_RAG_GTA/ground_truth_annotations.xlsx"
    
    # 결과 파일명에 타임스탬프 추가
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"backend/data/HR_RAG/HR_RAG_result/HR_RAG_result_{timestamp}.json"
    
    # 절대 경로로 변환 (실행 위치에 따라 다를 수 있음)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    input_full_path = os.path.join(base_dir, input_path)
    output_full_path = os.path.join(base_dir, output_path)
    
    evaluator.run_evaluation(input_full_path, output_full_path)
