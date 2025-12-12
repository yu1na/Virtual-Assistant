"""
상담 로깅 모듈
생성날짜: 2025.11.26
설명: RAG 상담 시스템의 로깅 및 스코어링 기능을 담당
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI

# stderr로 출력 (버퍼링 없음)
def debug_print(msg: str):
    """디버그 메시지를 stderr로 출력 (즉시 표시)"""
    print(msg, file=sys.stderr, flush=True)

class TherapyLogger:
    """상담 로깅 및 스코어링 클래스"""
    
    def __init__(self, openai_client: OpenAI, log_dir: str = None, log_file_prefix: str = "scoring_log"):
        """
        초기화
        
        Args:
            openai_client: OpenAI 클라이언트 인스턴스
            log_dir: 로그 파일 저장 디렉토리
            log_file_prefix: 로그 파일 접두사
        """
        self.openai_client = openai_client
        self.logger = None
        
        # ScoringLogger 임포트 및 초기화
        try:
            # councel/test 폴더의 scoring_logger 임포트
            if log_dir is None:
                base_dir = Path(__file__).parent.parent.parent  # backend/councel/
                log_dir = str(base_dir / "test")
            
            test_dir = Path(log_dir).resolve()  # 절대 경로로 변환
            scoring_logger_path = test_dir / "scoring_logger.py"
            
            # 파일 존재 확인
            if not scoring_logger_path.exists():
                debug_print(f"[경고] scoring_logger.py 파일을 찾을 수 없습니다: {scoring_logger_path}")
                return
            
            # 경로를 sys.path에 추가
            if str(test_dir) not in sys.path:
                sys.path.insert(0, str(test_dir))
            
            # 동적 임포트
            import importlib.util
            spec = importlib.util.spec_from_file_location("scoring_logger", test_dir / "scoring_logger.py")
            if spec and spec.loader:
                scoring_logger_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(scoring_logger_module)
                ScoringLogger = scoring_logger_module.ScoringLogger
                
                # 로거 초기화
                self.logger = ScoringLogger(log_dir=log_dir, log_file_prefix=log_file_prefix)
            else:
                 debug_print(f"[경고] ScoringLogger를 임포트할 수 없습니다.")
        except Exception as e:
            debug_print(f"[경고] 로거 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def is_available(self) -> bool:
        """로거 사용 가능 여부"""
        return self.logger is not None
    
    def evaluate_response_quality(self, user_input: str, answer: str, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        LLM 기반 답변 품질 평가
        
        Args:
            user_input: 사용자 질문
            answer: 상담사 답변
            retrieved_chunks: 검색된 청크 리스트
            
        Returns:
            평가 결과 딕셔너리 (relevance, accuracy, empathy, practicality, total, comment)
        """
        # 사용된 청크 정보 구성
        chunks_info = "\n".join([
            f"- {chunk['metadata'].get('source', '알 수 없음')}: {chunk['text'][:200]}..."
            for chunk in retrieved_chunks[:2]
        ])
        
        evaluation_prompt = f"""
        
                다음 상담 대화를 평가해주세요.

                사용자 질문: {user_input}

                상담사 답변: {answer}

                참고한 자료:
                {chunks_info}

                다음 4가지 기준으로 각각 1-10점으로 평가하고, JSON 형식으로 답변해주세요:

                1. 관련성(relevance): 질문과 답변의 관련성
                   - 사용자의 질문에 직접적으로 답변하는가?
                   - 질문의 핵심을 파악했는가?

                2. 정확성(accuracy): 참고 자료를 바탕으로 한 답변의 정확성
                   - 아들러 심리학 이론을 정확히 적용했는가?
                   - 참고 자료의 내용을 올바르게 반영했는가?

                3. 공감도(empathy): 사용자 감정에 대한 공감과 이해 ⭐ 중요
                   - 사용자의 감정을 먼저 인정하고 공감했는가?
                   - "~하셨군요", "~느끼시는군요" 등 반영적 경청 기법을 사용했는가?
                   - 감정을 판단하거나 최소화하지 않고 있는 그대로 받아들였는가?
                   - "하지만", "그래도" 등으로 감정을 부정하지 않았는가?
                   - 따뜻하고 수용적인 톤을 유지했는가?

                4. 실용성(practicality): 실제로 도움이 되는 조언인지
                   - 구체적이고 실천 가능한 방향을 제시했는가?
                   - 격려와 희망을 주는가?

                **공감도 평가 기준 (특히 중요):**
                - 10점: 감정을 완벽히 인정하고, 반영적 경청 사용, 3단계 구조 완벽
                - 8-9점: 감정 인정 우수, 공감 표현 명확
                - 6-7점: 감정 인정은 있으나 약간 부족
                - 4-5점: 감정 인정이 형식적이거나 불충분
                - 1-3점: 감정을 무시하거나 판단함

                JSON 형식 (다른 텍스트 없이 JSON만 출력):
                {{
                "relevance": 점수,
                "accuracy": 점수,
                "empathy": 점수,
                "practicality": 점수,
                "total": 총점,
                "comment": "간단한 평가 코멘트 (특히 공감도 관련)"
                }}
                
            """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 심리 상담 품질을 평가하는 전문가입니다. 객관적이고 공정하게 평가해주세요."
                    },
                    {
                        "role": "user",
                        "content": evaluation_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            # JSON 파싱
            eval_text = response.choices[0].message.content.strip()
            # JSON 블록에서 추출
            if "```json" in eval_text:
                eval_text = eval_text.split("```json")[1].split("```")[0].strip()
            elif "```" in eval_text:
                eval_text = eval_text.split("```")[1].split("```")[0].strip()
            
            evaluation = json.loads(eval_text)
            return evaluation
            
        except Exception as e:
            print(f"[경고] 답변 평가 실패: {e}")
            return {
                "relevance": 0,
                "accuracy": 0,
                "empathy": 0,
                "practicality": 0,
                "total": 0,
                "comment": "평가 실패"
            }
    
    def log_conversation(self, user_input: str, response: Dict[str, Any], retrieved_chunks: List[Dict[str, Any]], enable_scoring: bool = False) -> Dict[str, Any]:
        """
        대화 로그 저장 (스코어링 + 로그 저장)
        
        Args:
            user_input: 사용자 질문
            response: 답변 응답 딕셔너리
            retrieved_chunks: 검색된 청크 리스트
            enable_scoring: 스코어링 활성화 여부
            
        Returns:
            업데이트된 response (scoring 포함)
        """
        # 로거가 없거나 필수 데이터가 없으면 로그 저장 안 함
        if not self.is_available():
            debug_print(f"[경고] 로거가 초기화되지 않았습니다.")
            return response
        
        if not retrieved_chunks or not response.get("answer"):
            if not retrieved_chunks:
                 debug_print(f"[디버그] Vector DB에서 데이터를 찾지 못했습니다. 로그 저장하지 않음.")
            elif not response.get("answer"):
                 debug_print(f"[디버그] 답변이 없습니다. 로그 저장하지 않음.")
            return response
        
        # 스코어링 결과 준비
        if enable_scoring:
            # 실제 LLM 기반 스코어링 실행
            try:
                scoring_result = self.evaluate_response_quality(user_input, response["answer"], retrieved_chunks)
                response["scoring"] = scoring_result
            except Exception as e:
                print(f"[경고] 스코어링 실패: {e}")
                import traceback
                traceback.print_exc()
                # 스코어링 실패 시 기본값
                scoring_result = {
                    "relevance": 0,
                    "accuracy": 0,
                    "empathy": 0,
                    "practicality": 0,
                    "total": 0,
                    "comment": "스코어링 실패"
                }
        else:
            # 스코어링 비활성화 시 기본값 사용
            print(f"[디버그] 스코어링 비활성화 - 기본값 사용")
            scoring_result = {
                "relevance": 0,
                "accuracy": 0,
                "empathy": 0,
                "practicality": 0,
                "total": 0,
                "comment": "스코어링 비활성화"
            }
        
        # used_chunks_detailed가 없으면 빈 리스트로 설정
        if not response.get("used_chunks_detailed"):
            print(f"[경고] used_chunks_detailed가 없습니다. 빈 리스트로 설정합니다.")
            response["used_chunks_detailed"] = []
        
        # 로그 저장
        try:
            # metadata 구성
            metadata_dict = {
                "mode": response.get("mode", "unknown"),
                "enable_scoring": enable_scoring
            }
            
            # 최고 유사도 점수 추가 (있는 경우)
            similarity_score = response.get("similarity_score")
            if similarity_score is not None:
                metadata_dict["max_similarity"] = similarity_score
            
            self.logger.log_test_result(
                question=user_input,
                answer=response["answer"],
                chunks_used=response.get("used_chunks_detailed", []),
                scoring=scoring_result,
                metadata=metadata_dict
            )
        except Exception as e:
            debug_print(f"[경고] 로그 저장 실패: {e}")
            import traceback
            traceback.print_exc()
        
        return response

