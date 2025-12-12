"""
답변 생성 모듈
생성날짜: 2025.12.01
설명: LLM 기반 답변 생성 기능
시간복잡도: O(k)
"""

import asyncio
from typing import List, Dict, Any, Optional
from openai import OpenAI
from openai import AsyncOpenAI

# 답변 생성 클래스
class ResponseGenerator:

    # 초기화 함수    
    def __init__(self, openai_client: OpenAI, counseling_keywords: List[str], async_openai_client: Optional[AsyncOpenAI] = None):

        # OpenAI, 상담 키워드
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
        self.counseling_keywords = counseling_keywords
        # 키워드 매칭 최적화: 리스트를 set으로 변환하여 O(1) 조회 가능
        self.counseling_keywords_set = set(keyword.lower() for keyword in counseling_keywords)
    
    # 사용자 입력에 감정 + 상황 설명이 있는지 판단하는 함수
    def has_situation_context(self, user_input: str) -> bool:
        
        user_input_lower = user_input.lower()
        
        # 감정 키워드
        emotion_keywords = [
            '힘들', '어렵', '괴롭', '슬프', '화나', '우울', '불안', '답답', 
            '스트레스', '고통', '절망', '무기력', '초조', '걱정', '두려움',
            '짜증', '분노', '상처', '아픔', '외로움', '허탈', '실망'
        ]
        
        # 상황 설명 키워드 (구체적인 사건/상황을 나타내는 단어)
        situation_keywords = [
            # 직장/일 관련
            '직장', '회사', '동료', '상사', '부장', '과장', '팀장', '업무', '일', '프로젝트',
            # 관계 관련
            '가족', '부모', '아버지', '어머니', '형제', '자매', '친구', '연인', '배우자', '이혼',
            # 상황 설명 패턴
            '때문에', '해서', '해서인지', '했는데', '했어', '했어요', '일어났', '발생했', '경험했',
            '문제', '상황', '일', '사건', '때', '순간', '경우', '상황이', '문제가',
            # 구체적 명사
            '시험', '면접', '취업', '전입', '이사', '결혼', '이별', '병', '질병', '사고'
        ]
        
        # 감정 키워드가 있는지 확인
        has_emotion = any(keyword in user_input_lower for keyword in emotion_keywords)
        
        # 상황 설명 키워드가 있는지 확인
        has_situation = any(keyword in user_input_lower for keyword in situation_keywords)
        
        # 감정 + 상황 설명이 모두 있으면 상세한 입력으로 판단
        return has_emotion and has_situation
    
    # 입력이 충분히 구체적인 상황 설명인지 판단하는 함수
    def is_sufficiently_detailed(self, user_input: str) -> bool:

        user_input_lower = user_input.lower()
        
        # 구체적인 상황 설명 패턴들
        # 1. 누가(who) + 무엇(what) 패턴: 명확한 인물 + 구체적 행동/사건
        specific_patterns = [
            # ~가/이 ~했다 패턴
            r'\w+가.*말했|말씀|이야기|말하',
            r'\w+이.*말했|말씀|이야기|말하',
            r'\w+가.*했다|했어|했대|했는데',
            r'\w+이.*했다|했어|했대|했는데',
            # ~때문에, ~해서 패턴 (인과관계 설명)
            r'\w+때문에.*\w+',
            r'\w+해서.*\w+',
            # 구체적 행동 설명
            r'\w+가.*\w+에게.*말했|말씀',
            r'\w+가.*\w+한테.*말했|말씀',
            # 사건 설명
            r'\w+일어났|발생했|있었|생겼',
        ]
        
        import re
        for pattern in specific_patterns:
            if re.search(pattern, user_input_lower):
                # 패턴이 매칭되고, 길이가 충분한지 확인 (너무 짧으면 구체적이지 않음)
                if len(user_input) > 15:  # 최소 15자 이상
                    return True
        
        # 구체적인 명사 조합 확인 (인물 + 행동)
        people_keywords = ['상사', '사장', '부장', '과장', '팀장', '동료', '부모', '아버지', '어머니', '친구', '연인']
        action_keywords = ['말했', '했다', '했어', '했대', '했는데', '했다고', '했다는', '이야기', '말씀']
        
        has_person = any(person in user_input_lower for person in people_keywords)
        has_action = any(action in user_input_lower for action in action_keywords)
        
        # 인물과 행동이 모두 있고, 충분한 길이면 구체적으로 판단
        if has_person and has_action and len(user_input) > 15:
            return True
        
        # 구체적인 상황 설명 키워드가 많이 포함된 경우
        detailed_keywords = ['때문에', '해서', '해서인지', '했는데', '일어났', '발생했', '경험했', '했다고', '했다는']
        detailed_count = sum(1 for keyword in detailed_keywords if keyword in user_input_lower)
        
        if detailed_count >= 2 and len(user_input) > 15:  # 2개 이상의 구체적 키워드
            return True
        
        return False
    
    # 대화 히스토리에서 이미 상황이 설명되었는지 확인하는 함수
    def has_situation_in_history(self, chat_history: List[Dict[str, str]]) -> bool:

        if not chat_history:
            return False
        
        # 상황 설명 키워드
        situation_keywords = [
            '상사', '동료', '부장', '과장', '팀장', '직장', '회사', '일어났', '발생했',
            '문제', '상황', '사건', '때문에', '했는데', '했어', '했어요', '경험했',
            '말했', '말했대', '말했어', '말씀드렸', '말했어요', '했다고', '했다는', '했대', '말씀',
            '가족', '부모', '아버지', '어머니', '친구', '연인', '배우자'
        ]
        
        # 감정 키워드
        emotion_keywords = [
            '화나', '짜증', '힘들', '어렵', '괴롭', '슬프', '우울', '불안', 
            '답답', '스트레스', '고통', '절망', '분노', '상처'
        ]
        
        # 최근 대화에서 상황 설명 확인 (최근 5개까지 확인)
        for history in chat_history[-5:]:
            user_text = history["user"].lower()
            # 상황 키워드와 감정 키워드가 모두 있는지 확인
            has_situation_kw = any(keyword in user_text for keyword in situation_keywords)
            has_emotion_kw = any(keyword in user_text for keyword in emotion_keywords)
            if has_situation_kw and has_emotion_kw:
                return True
        return False
    
    # 히스토리에서 설명된 상황을 요약하는 함수
    def extract_situation_from_history(self, chat_history: List[Dict[str, str]]) -> str:

        if not chat_history:
            return ""
        
        # 상황이 있는 대화들 추출
        situation_contexts = []
        situation_keywords = [
            '상사', '동료', '부장', '과장', '팀장', '직장', '회사', '일어났', '발생했',
            '문제', '상황', '사건', '때문에', '했는데', '했어', '경험했',
            '말했', '말했대', '말했어', '말씀드렸', '말했어요', '했다고', '했다는', '했대',
            '가족', '부모', '아버지', '어머니', '친구', '연인', '배우자'
        ]
        
        for history in chat_history[-5:]:
            user_text = history["user"]
            user_text_lower = user_text.lower()
            if any(keyword in user_text_lower for keyword in situation_keywords):
                # 감정 표현도 함께 있는 경우만 포함
                emotion_keywords = ['화나', '짜증', '힘들', '어렵', '괴롭', '슬프']
                if any(emotion in user_text_lower for emotion in emotion_keywords):
                    situation_contexts.append(user_text)
        
        if situation_contexts:
            # 최근 상황부터 역순으로 정리하여 요약
            return " | ".join(situation_contexts[-2:])  # 최근 2개만 포함
        return ""
    
    # 사용자 입력 분류(set 연산 사용)
    def classify_input(self, user_input: str) -> str:

        user_input_lower = user_input.lower()
        user_words = set(user_input_lower.split())
        
        # 아들러 키워드 체크
        if "아들러" in user_input or "adler" in user_input_lower:
            return "adler"
        
        # 감정/상담 키워드 체크 (set 연산으로 최적화)
        # 단어 단위 매칭 시도
        if user_words & self.counseling_keywords_set:
            return "counseling"
        
        # 부분 문자열 매칭 (하위 호환성)
        for keyword in self.counseling_keywords_set:
            if keyword in user_input_lower:
                return "counseling"
        
        return "general"
    
    # 입력된 질문이 심리 상담 관련인지 확인하는 함수
    def is_therapy_related(self, user_input: str) -> bool:
        input_type = self.classify_input(user_input)
        return input_type in ["adler", "counseling"]
    
    # RAG없이 LLM만으로 답변 생성 (프로토콜 통합)
    async def _generate_llm_only_response(self, user_input: str, protocol_persona: str, chat_history: List[Dict[str, str]], counseling_keywords: List[str], protocol_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        try:
            # 프로토콜 통합 페르소나 사용
            persona_prompt = protocol_persona
            
            # 대화 히스토리에서 감정 맥락 파악 (최적화: set 연산 사용)
            emotion_context = ""
            if chat_history:
                recent_emotions = []
                counseling_keywords_set = set(kw.lower() for kw in counseling_keywords[:30])  # 주요 감정 키워드만
                for history in chat_history[-2:]:
                    # 최근 대화에서 감정 키워드 추출 (set 연산으로 최적화)
                    history_words = set(history["user"].lower().split())
                    matched = history_words & counseling_keywords_set
                    if matched:
                        recent_emotions.extend(list(matched)[:3])
                
                if recent_emotions:
                    emotion_context = f"\n[이전 대화 맥락: 사용자가 '{', '.join(set(recent_emotions[:3]))}' 관련 감정을 표현했습니다. 이를 고려하여 답변하세요.]"
            
            # 히스토리에서 이미 상황이 설명되었는지 확인
            has_situation_in_history = self.has_situation_in_history(chat_history)
            situation_from_history = ""
            history_situation_guidance = ""
            
            if has_situation_in_history:
                # 히스토리에서 상황 추출
                situation_from_history = self.extract_situation_from_history(chat_history)
                
                # 현재 입력이 해결 방법을 묻는 질문인지 확인
                solution_keywords = ['어떻게 해야', '어떻게 하면', '어떻게 해야할까', '어떻게 해야할지', 
                                     '어떻게 해야 할지', '방법', '해결', '대처', '알려줘', '알려줘요', 
                                     '알려주세요', '조언', '도움']
                user_input_lower = user_input.lower()
                is_asking_solution = any(keyword in user_input_lower for keyword in solution_keywords)
                
                if is_asking_solution:
                    # 해결 방법을 묻는 경우: 히스토리의 상황을 바탕으로 해결 방법 제시
                    history_situation_guidance = f"""
[절대 중요: 이전 대화에서 사용자가 이미 구체적인 상황을 설명했습니다!
상황 내용: {situation_from_history}

현재 질문("{user_input}")은 그 상황에 대한 해결 방법을 묻는 것입니다.

**반드시 준수:**
1. 절대 다시 상황을 물어보지 마세요. "어떤 상황인지", "구체적으로", "상황을 알려주세요" 같은 표현은 완전히 금지입니다.
2. 이미 설명된 상황({situation_from_history})을 바탕으로 즉시 구체적인 해결 방법을 제시하세요.
3. 감정 인정(1문장) + 구체적인 해결 방법(2-3문장) 형식으로 답변하세요.

**절대 금지 표현:**
- "어떤 상황인지 알려주세요"
- "구체적으로 말씀해 주시면"
- "상황을 설명해 주세요"
- "어떤 일이 있었는지"
- "예를 들어, 업무, 개인 생활..."

이런 표현들은 절대 사용하지 마세요! 즉시 해결 방법을 제시하세요.]
"""
                else:
                    # 해결 방법을 묻지 않는 경우: 상황이 이미 설명되었음을 인지하고 답변
                    history_situation_guidance = f"""
[참고: 이전 대화에서 사용자가 이미 상황을 설명했습니다: {situation_from_history}
현재 입력과 연결하여 자연스럽게 답변하세요. 중복 질문은 피하세요]
"""
            
            # 대화 히스토리 추가 (최적화: 최근 3개 포함으로 증가 - 상황 파악을 위해)
            messages = [{"role": "system", "content": persona_prompt + emotion_context + history_situation_guidance}]
            
            # 최근 3개의 대화 포함 (상황 파악을 위해 2개 → 3개로 증가)
            for history in chat_history[-3:]:
                messages.append({"role": "user", "content": history["user"]})
                messages.append({"role": "assistant", "content": history["assistant"]})
            
            # 사용자 입력이 구체적 상황을 포함하는지 확인
            is_detailed_input = self.has_situation_context(user_input)
            is_sufficiently_detailed = self.is_sufficiently_detailed(user_input) if is_detailed_input else False
            
            situation_guidance = ""
            if is_detailed_input and not has_situation_in_history:
                if is_sufficiently_detailed:
                    # 충분히 구체적인 상황이 이미 설명된 경우
                    situation_guidance = """
**충분히 구체적인 상황이 이미 제시된 경우:**
- 이미 구체적인 상황이 설명되었으므로 다시 상황을 물어보지 마세요
- "구체적으로 어떤 상황인지", "어떤 일이 있었는지" 같은 질문은 절대 하지 마세요
- 그 상황에 대한 공감과 함께 다음 단계(감정 탐색, 해결 방법 탐색 등)로 자연스럽게 진행하세요
- 예: "그런 상황이 정말 화가 나셨겠어요. 그때 어떤 기분이셨나요?" 또는 "그 상황에서 지금 가장 힘든 부분은 무엇인가요?"
"""
                else:
                    # 상황은 언급되었지만 충분히 구체적이지 않은 경우
                    situation_guidance = """
**상황이 언급되었으나 충분히 구체적이지 않은 경우:**
- 구체적인 상황에 대해 더 자세히 물어보는 질문을 포함하세요
- 예: "구체적으로 어떤 상황이었는지 말씀해 주실 수 있을까요?"
- "언제든지 말씀해주세요", "더 이야기하고 싶으시면" 같은 마무리 표현은 절대 사용하지 마세요
"""
            elif not is_detailed_input and not has_situation_in_history:
                # 현재 입력에도 상황이 없고 히스토리에도 없는 경우
                situation_guidance = """
**상황 설명이 없는 경우:**
- 사용자가 상황을 설명하도록 자연스럽게 유도하는 질문을 포함하세요
"""
            
            # 공감적 답변 유도 프롬프트 (프로토콜 통합)
            enhanced_input = f"""{user_input}

[중요: 반드시 다음 구조로 답변하세요 - 2~3문장으로 적절한 길이로 작성]
1. 먼저 사용자의 감정을 인정하고 공감 (1문장, 필수)
   예: "힘드시는 마음 충분히 이해됩니다"
   예: "그런 마음이 드시는군요"

2. 상황에 맞는 자연스러운 질문 또는 공감문 (1~2문장)
   - 고정된 질문이 아니라 사용자의 상황에 맞게 자연스럽게 질문하세요
   - 현재 상담 단계의 지침을 참고하되, 자연스러운 표현을 사용하세요
   - 이미 충분히 구체적인 상황이 설명되었다면, 그 상황을 다시 물어보지 말고 감정이나 해결 방법에 대해 질문하세요
   - 상황이 구체적이지 않은 경우에만 더 자세한 상황을 물어보세요

{situation_guidance}
**절대 준수 사항**: 
- 총 2~3문장으로 적절한 길이로 작성하세요
- 공감(1단계)은 필수입니다
- 재해석 단계는 포함하지 마세요
- 고정된 질문이 아니라 상황에 맞는 자연스러운 질문을 하세요
- "언제든지 말씀해주세요", "더 이야기하고 싶으시면", "언제든 다시 찾아주세요" 같은 마무리/종료 표현은 절대 사용하지 마세요
- 상담을 계속 이어가도록 하는 질문을 포함하세요"""
            
            messages.append({"role": "user", "content": enhanced_input})
            
            # OpenAI API 호출 (최적화: max_tokens 조정)
            if self.async_openai_client:
                response = await self.async_openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3,  # 일관된 답변을 위해 낮은 temperature 유지
                    max_tokens=180  # 토큰 수 최적화 (2~3문장)
                )
            else:
                # Fallback: 동기 클라이언트 사용
                response = await asyncio.to_thread(
                    self.openai_client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=180
                )
            
            answer = response.choices[0].message.content.strip()
            
            return {
                "answer": answer,
                "used_chunks": [],
                "used_chunks_detailed": [],
                "mode": "llm_only",
                "continue_conversation": True,
                "similarity_score": None  # LLM only 모드에서는 유사도 없음
            }
        
        except Exception as e:
            print(f"[오류] LLM 단독 답변 생성 실패")
            return {
                "answer": "죄송합니다. 답변 생성 중 오류가 발생했습니다. 다시 시도해주세요.",
                "used_chunks": [],
                "used_chunks_detailed": [],
                "mode": "error",
                "continue_conversation": True
            }
    
    # 페르소나 기반 답변 생성 (RAG 기반, 프로토콜 통합)
    async def generate_response_with_persona(self, user_input: str, retrieved_chunks: List[Dict[str, Any]], 
                                            protocol_persona: str, chat_history: List[Dict[str, str]], mode: str = "adler", 
                                            distance_to_similarity_func=None, summarize_chunk_func=None, protocol_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        # 검색된 청크가 없는 경우
        if not retrieved_chunks:
            return {
                "answer": "죄송합니다. 관련된 자료를 찾을 수 없습니다. 다른 질문을 해주시겠어요?",
                "used_chunks": [],
                "used_chunks_detailed": [],
                "continue_conversation": True
            }
        
        # 컨텍스트 구성
        context_parts = []
        used_chunks = []
        used_chunks_detailed = []
        
        for i, chunk in enumerate(retrieved_chunks[:3], 1):  # 상위 3개 청크 사용
            chunk_text = chunk['text']
            source = chunk['metadata'].get('source', '알 수 없음')
            context_parts.append(f"[자료 {i}]\n{chunk_text}\n(출처: {source})")
            used_chunks.append(f"{source}: {chunk_text[:50]}...")
            
            # 상세 청크 정보 (로깅용)
            if summarize_chunk_func:
                chunk_summary = summarize_chunk_func(chunk_text)
            else:
                chunk_summary = chunk_text[:100] + "..."
            
            chunk_distance = chunk.get('distance')
            if distance_to_similarity_func and chunk_distance is not None:
                chunk_similarity = distance_to_similarity_func(chunk_distance)
            else:
                chunk_similarity = None
            
            used_chunks_detailed.append({
                "chunk_id": chunk['id'],
                "source": source,
                "metadata": chunk['metadata'],
                "summary_kr": chunk_summary,
                "distance": chunk_distance,
                "similarity": chunk_similarity  # 코사인 유사도 추가
            })
        
        context = "\n\n".join(context_parts)
        
        # 사용자 입력에서 감정 키워드 추출 (최적화: set 연산 사용)
        detected_emotions = []
        user_input_lower = user_input.lower()
        user_words = set(user_input_lower.split())
        
        # 주요 감정 키워드 set 생성
        main_keywords_set = set(kw.lower() for kw in self.counseling_keywords[:30])
        
        # 단어 단위 매칭 (set 연산으로 최적화)
        matched = user_words & main_keywords_set
        if matched:
            detected_emotions.extend(list(matched)[:3])
        
        # 부분 문자열 매칭 (하위 호환성)
        if not detected_emotions:
            for keyword in main_keywords_set:
                if keyword in user_input_lower:
                    detected_emotions.append(keyword)
                    if len(detected_emotions) >= 3:
                        break
        
        emotion_note = ""
        if detected_emotions:
            emotion_note = f"\n[감지된 감정: {', '.join(detected_emotions[:3])} - 이 감정들을 먼저 인정하고 공감해주세요]"
        
        # 프로토콜 통합 페르소나 사용
        persona_prompt = protocol_persona
        
        # 히스토리에서 이미 상황이 설명되었는지 확인
        has_situation_in_history = self.has_situation_in_history(chat_history)
        situation_from_history = ""
        history_situation_guidance = ""
        
        if has_situation_in_history:
            # 히스토리에서 상황 추출
            situation_from_history = self.extract_situation_from_history(chat_history)
            
            # 현재 입력이 해결 방법을 묻는 질문인지 확인
            solution_keywords = ['어떻게 해야', '어떻게 하면', '어떻게 해야할까', '어떻게 해야할지', 
                                 '어떻게 해야 할지', '방법', '해결', '대처', '알려줘', '알려줘요', 
                                 '알려주세요', '조언', '도움']
            user_input_lower = user_input.lower()
            is_asking_solution = any(keyword in user_input_lower for keyword in solution_keywords)
            
            if is_asking_solution:
                # 해결 방법을 묻는 경우: 히스토리의 상황을 바탕으로 해결 방법 제시
                history_situation_guidance = f"""
[절대 중요: 이전 대화에서 사용자가 이미 구체적인 상황을 설명했습니다!
상황 내용: {situation_from_history}

현재 질문("{user_input}")은 그 상황에 대한 해결 방법을 묻는 것입니다.

**반드시 준수:**
1. 절대 다시 상황을 물어보지 마세요. "어떤 상황인지", "구체적으로", "상황을 알려주세요" 같은 표현은 완전히 금지입니다.
2. 이미 설명된 상황({situation_from_history})을 바탕으로 참고 자료를 활용하여 즉시 구체적인 해결 방법을 제시하세요.
3. 감정 인정(1문장) + 참고 자료 기반 조언(2-3문장) + 구체적인 해결 방법(1-2문장) 형식으로 답변하세요.

**절대 금지 표현:**
- "어떤 상황인지 알려주세요"
- "구체적으로 말씀해 주시면"
- "상황을 설명해 주세요"
- "어떤 일이 있었는지"
- "예를 들어, 업무, 개인 생활..."

이런 표현들은 절대 사용하지 마세요! 즉시 해결 방법을 제시하세요.]
"""
            else:
                # 해결 방법을 묻지 않는 경우: 상황이 이미 설명되었음을 인지하고 답변
                history_situation_guidance = f"""
[참고: 이전 대화에서 사용자가 이미 상황을 설명했습니다: {situation_from_history}
현재 입력과 연결하여 자연스럽게 답변하세요. 중복 질문은 피하세요]
"""
        
        # 사용자 입력 내용 분석 (답변 구조 결정)
        is_detailed_input = self.has_situation_context(user_input)  # 감정 + 상황 설명이 있으면 상세한 입력으로 판단
        is_sufficiently_detailed = self.is_sufficiently_detailed(user_input) if is_detailed_input else False
        
        # 답변 구조 (재해석 단계 제거)
        # 구체적 상황이 포함된 경우 추가 안내
        situation_guidance = ""
        if is_detailed_input and not has_situation_in_history:
            if is_sufficiently_detailed:
                # 충분히 구체적인 상황이 이미 설명된 경우
                situation_guidance = """
**충분히 구체적인 상황이 이미 제시된 경우:**
- 이미 구체적인 상황이 설명되었으므로 다시 상황을 물어보지 마세요
- "구체적으로 어떤 상황인지", "어떤 일이 있었는지" 같은 질문은 절대 하지 마세요
- 참고 자료를 바탕으로 그 상황에 대한 공감과 함께 구체적인 조언과 해결 방법을 제시하세요
- 예: "그런 상황이 정말 화가 나셨겠어요. (참고 자료 기반 조언) 그 상황에서 지금 가장 힘든 부분은 무엇인가요?"
"""
            else:
                # 상황은 언급되었지만 충분히 구체적이지 않은 경우
                situation_guidance = """
**상황이 언급되었으나 충분히 구체적이지 않은 경우 (예: 상사가 괴롭힘, 관계 문제 등):**
- 구체적인 상황에 대해 더 자세히 물어보는 질문을 포함하세요
- 예: "구체적으로 어떤 상황이었는지 말씀해 주실 수 있을까요?"
- 예: "그때 어떤 일이 있었는지 더 자세히 들려주실 수 있을까요?"
- "언제든지 말씀해주세요", "더 이야기하고 싶으시면" 같은 마무리 표현은 절대 사용하지 마세요
- 상담을 계속 진행하도록 하는 질문을 반드시 포함하세요
"""
        elif not is_detailed_input and not has_situation_in_history:
            # 현재 입력에도 상황이 없고 히스토리에도 없는 경우
            situation_guidance = """
**상황 설명이 없는 경우:**
- 사용자가 상황을 설명하도록 자연스럽게 유도하는 질문을 포함하세요
"""
        
        answer_structure = f"""**답변 구조 (반드시 이 순서대로, 참고 자료를 바탕으로 상세하게 작성):**

1단계 - 감정 인정 및 공감 (1~2문장):
   - 사용자의 감정을 있는 그대로 인정하고 공감합니다.
   - 예: "힘드시는 마음 충분히 이해됩니다"
   - 예: "그런 마음이 드시는군요"
   - 절대 "하지만", "그래도"로 시작하지 마세요.

2단계 - 참고 자료를 바탕으로 한 통찰 또는 조언 (2~3문장):
   - 검색된 자료의 내용을 바탕으로 구체적이고 실용적인 조언을 제공하세요
   - 아들러 심리학의 원칙을 자연스럽게 통합하여 설명하세요
   - 사용자의 상황에 맞게 자료의 내용을 적용하여 설명하세요

3단계 - 자연스러운 질문 또는 다음 단계 제안 (1~2문장):
   - 고정된 질문이 아니라 사용자의 상황에 맞게 자연스럽게 질문하세요
   - 현재 상담 단계의 지침을 참고하되, 자연스러운 표현을 사용하세요
   - 이미 충분히 구체적인 상황이 설명되었다면, 그 상황을 다시 물어보지 말고 감정이나 해결 방법에 대해 질문하세요
   - 상황이 구체적이지 않은 경우에만 더 자세한 상황을 물어보세요

{situation_guidance}
**절대 준수 사항:**
- 참고 자료를 바탕으로 상세하고 구체적인 답변을 작성하세요 (총 4~7문장)
- 공감(1단계)은 필수입니다
- 참고 자료의 내용을 반드시 활용하여 답변하세요
- 고정된 질문이 아니라 상황에 맞는 자연스러운 질문을 하세요
- "언제든지 말씀해주세요", "더 이야기하고 싶으시면", "언제든 다시 찾아주세요" 같은 마무리/종료 표현은 절대 사용하지 마세요
- 상담을 계속 이어가도록 하는 질문을 포함하세요
"""
        
        user_message = f"""참고 자료:
{context}

사용자 질문: {user_input}{emotion_note}

{answer_structure}
- 참고 자료의 내용을 충분히 활용하여 상세하고 구체적으로 답변하세요
- 실천 방안은 구체적이고 즉시 실행 가능해야 함
- 문제보다는 해결책, 약점보다는 강점에 초점
- 감정을 판단하거나 최소화하지 않기
- 따뜻하고 수용적인 톤 유지
- 구체적인 상황(예: 상사, 관계, 직장 문제)이 언급되면 반드시 그에 대한 구체적인 질문을 포함하세요
- "언제든지", "말씀해주세요", "더 이야기하고 싶으시면" 같은 마무리 표현은 절대 사용하지 마세요"""
        
        # 대화 히스토리 추가 (단기 기억, 히스토리 상황 파악을 위해 최근 3개 포함)
        messages = [{"role": "system", "content": persona_prompt + history_situation_guidance}]
        
        # 최근 3개의 대화 포함 (상황 파악을 위해 5개 → 3개로 조정, 하지만 히스토리 가이던스로 보완)
        for history in chat_history[-3:]:
            messages.append({"role": "user", "content": history["user"]})
            messages.append({"role": "assistant", "content": history["assistant"]})
        
        messages.append({"role": "user", "content": user_message})
        
        # OpenAI API 호출 (최적화: max_tokens 조정)
        try:
            if self.async_openai_client:
                response = await self.async_openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3,  # 낮은 temperature로 일관된 답변 생성
                    max_tokens=400  # 답변 길이 최적화 (RAG 사용 시 상세하게 4~7문장)
                )
            else:
                # Fallback: 동기 클라이언트 사용
                response = await asyncio.to_thread(
                    self.openai_client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=400
                )
            
            answer = response.choices[0].message.content.strip()
            
            return {
                "answer": answer,
                "used_chunks": used_chunks,
                "used_chunks_detailed": used_chunks_detailed,
                "mode": mode,
                "continue_conversation": True
            }
        
        except Exception as e:
            print(f"[오류] OpenAI 답변 생성 실패: {e}")
            return {
                "answer": "죄송합니다. 답변 생성 중 오류가 발생했습니다. 다시 시도해주세요.",
                "used_chunks": [],
                "used_chunks_detailed": [],
                "mode": mode,
                "continue_conversation": True
            }