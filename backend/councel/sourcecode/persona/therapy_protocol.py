"""
상담 프로토콜 모듈
생성날짜: 2025.12.05
설명: EAP(Employee Assistance Program) + SFBT(Solution-Focused Brief Therapy) 통합 프로토콜
"""

import asyncio
from typing import Dict, Any, List, Optional
from enum import Enum
from openai import OpenAI
from openai import AsyncOpenAI


# 상담 단계 (4단계)
class TherapyStage(Enum):
    EMOTION_EXPLORATION = "emotion_exploration"  # 1. 감정 탐색
    STRENGTH_RESOURCES = "strength_resources"  # 2. 강점/자원 찾기
    SOLUTION_FOCUSED = "solution_focused"  # 3. 해결 중심 질문
    ACTION_PLAN = "action_plan"  # 4. 작은 행동 계획


# 프로토콜 유형
class ProtocolType(Enum):
    EAP = "eap"  # EAP 프로토콜
    SFBT = "sfbt"  # SFBT 프로토콜
    INTEGRATED = "integrated"  # 통합 프로토콜


# 상담 세션 상태를 추적하는 클래스
class TherapySession:
    
    def __init__(self):
        self.current_stage: TherapyStage = TherapyStage.EMOTION_EXPLORATION
        self.protocol_type: ProtocolType = ProtocolType.INTEGRATED
        self.conversation_count: int = 0
        self.identified_issues: List[str] = []
        self.severity_level: Optional[str] = None  # low, medium, high, critical
        self.goals: List[str] = []
        self.strengths_found: List[str] = []  # 발견된 강점
        self.resources_found: List[str] = []  # 발견된 자원
        self.action_plans: List[str] = []  # 행동 계획
    
    # 대화 히스토리에서 세션 상태 업데이트하는 함수
    def update_from_history(self, chat_history: List[Dict[str, str]]):

        self.conversation_count = len(chat_history)

    # 세션 상태를 딕셔너리로 변환    
    # 딕셔너리: 키 값 형태로 이루어져있는 자료구조
    def to_dict(self) -> Dict[str, Any]:

        return {
            "current_stage": self.current_stage.value,
            "protocol_type": self.protocol_type.value,
            "conversation_count": self.conversation_count,
            "identified_issues": self.identified_issues,
            "severity_level": self.severity_level,
            "goals": self.goals,
            "strengths_found": self.strengths_found,
            "resources_found": self.resources_found,
            "action_plans": self.action_plans
        }


# EAP + SFBT 통합 프로토콜 관리 클래스
class TherapyProtocol:
    
    # 초기화 함수
    def __init__(self, openai_client: OpenAI, async_openai_client: Optional[AsyncOpenAI] = None):
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
        self.session = TherapySession()
        
        # 상담 단계별 지침
        self.stage_guidelines = {
            TherapyStage.EMOTION_EXPLORATION: {
                "focus": "감정 탐색",
                "guideline": "사용자의 감정/고통/불안/분노를 있는 그대로 인정하고 공감합니다. 감정을 판단하지 않고 수용합니다."
            },
            TherapyStage.STRENGTH_RESOURCES: {
                "focus": "강점/자원 찾기",
                "guideline": "사용자의 노력, 강점, 가치를 발견하고 인정합니다. 이미 가지고 있는 자원과 대처 능력을 탐색합니다."
            },
            TherapyStage.SOLUTION_FOCUSED: {
                "focus": "해결 중심 질문",
                "guideline": "해결 의지와 변화 욕구를 탐색합니다. 목표를 명확히 하고 작은 변화의 가능성을 찾습니다."
            },
            TherapyStage.ACTION_PLAN: {
                "focus": "작은 행동 계획",
                "guideline": "구체적이고 실천 가능한 작은 행동을 함께 계획합니다. 사용자가 주도적으로 선택하도록 돕습니다."
            }
        }
    
    # 대화 히스토리를 기반으로 세션 상태 업데이트
    def update_session(self, chat_history: List[Dict[str, str]]):
        self.session.update_from_history(chat_history)
    
    # 세션 상태 초기화
    def reset_session(self):
        self.session = TherapySession()
    
    # 사용자 상황에 따라 프로토콜 선택
    def select_protocol(self, user_input: str, chat_history: List[Dict[str, str]]) -> ProtocolType:
        
        # 대화 초기에는 EAP 중심
        if len(chat_history) <= 1:
            return ProtocolType.EAP
        
        # 위기 키워드 감지 시 EAP 우선
        crisis_keywords = ['죽고 싶', '자살', '자해', '끝내고 싶', '포기', '절망']
        if any(keyword in user_input for keyword in crisis_keywords):
            self.session.severity_level = "critical"
            return ProtocolType.EAP
        
        # 해결책 탐색 단계에서는 SFBT 중심
        solution_keywords = ['어떻게', '방법', '해결', '개선', '나아지', '변화']
        if any(keyword in user_input for keyword in solution_keywords):
            return ProtocolType.SFBT
        
        # 기본적으로 통합 프로토콜 사용
        return ProtocolType.INTEGRATED
    
    # 문제의 심각도 평가
    def assess_severity(self, user_input: str, chat_history: List[Dict[str, str]]) -> str:
        
        # 위기 상황 키워드
        critical_keywords = ['죽고 싶', '자살', '자해', '끝내고 싶']
        high_keywords = ['견딜 수 없', '미치겠', '한계', '더 이상 못', '불가능']
        medium_keywords = ['힘들', '어렵', '괴롭', '고통', '스트레스']
        
        user_input_lower = user_input.lower()
        
        if any(keyword in user_input_lower for keyword in critical_keywords):
            return "critical"
        elif any(keyword in user_input_lower for keyword in high_keywords):
            return "high"
        elif any(keyword in user_input_lower for keyword in medium_keywords):
            return "medium"
        else:
            return "low"
    
    # 사용자 입력에 감정 + 상황 설명이 있는지 체크
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
    
    # 단계별 가이드라인 가져오기
    def get_stage_guideline(self, stage: TherapyStage) -> Dict[str, str]:
        return self.stage_guidelines.get(stage, {})
    
    # LLM을 사용하여 사용자가 말한 문장 분석 및 적절한 단계 선택
    async def select_stage_with_llm(self, user_input: str, chat_history: List[Dict[str, str]]) -> TherapyStage:

        try:
            # 대화 히스토리 컨텍스트 구성 (최근 3개만)
            history_context = ""
            if chat_history:
                recent_history = chat_history[-3:]
                history_parts = []
                for h in recent_history:
                    history_parts.append(f"사용자: {h['user']}")
                    history_parts.append(f"상담사: {h['assistant']}")
                history_context = "\n".join(history_parts)
            
            # LLM에게 단계 선택 요청
            prompt = f"""당신은 EAP + SFBT 기법을 사용하는 아들러 기반 상담가입니다.
다음 규칙에 따라 '사용자 발화'를 분석하고 가장 적절한 상담 단계를 선택합니다.

[상담 단계]
1. 감정 탐색 (emotion_exploration)
2. 강점/자원 찾기 (strength_resources)
3. 해결 중심 질문 (solution_focused)
4. 작은 행동 계획 (action_plan)

[단계 선택 기준]
- 사용자가 감정/고통/불안/분노를 표현하면 → 1번
- 스스로의 노력·강점·가치에 대해 말하기 시작하면 → 2번
- 해결 의지, 변화 욕구, 목표 언급 시 → 3번
- 대화를 마무리하거나 실행 의지가 보일 때 → 4번

[이전 대화 맥락]
{history_context if history_context else "(첫 대화입니다)"}

[사용자 발화]
{user_input}

위 발화를 분석하여 가장 적절한 단계 번호만 출력하세요 (1, 2, 3, 또는 4):"""

            if self.async_openai_client:
                response = await self.async_openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "당신은 상담 단계를 선택하는 전문가입니다. 반드시 1, 2, 3, 4 중 하나의 숫자만 출력하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=10
                )
            else:
                # Fallback: 동기 클라이언트 사용
                response = await asyncio.to_thread(
                    self.openai_client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "당신은 상담 단계를 선택하는 전문가입니다. 반드시 1, 2, 3, 4 중 하나의 숫자만 출력하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=10
                )
            
            stage_number = response.choices[0].message.content.strip()
            
            # 숫자를 TherapyStage로 변환
            stage_map = {
                "1": TherapyStage.EMOTION_EXPLORATION,
                "2": TherapyStage.STRENGTH_RESOURCES,
                "3": TherapyStage.SOLUTION_FOCUSED,
                "4": TherapyStage.ACTION_PLAN
            }
            
            selected_stage = stage_map.get(stage_number, TherapyStage.EMOTION_EXPLORATION)
            return selected_stage
            
        except Exception as e:
            print(f"[경고] LLM 단계 선택 실패, 기본 단계 사용")
            # 실패 시 첫 대화면 감정 탐색, 아니면 현재 단계 유지
            if len(chat_history) == 0:
                return TherapyStage.EMOTION_EXPLORATION
            else:
                return self.session.current_stage
    
    # 프로토콜 기반 상담 가이드 생성
    async def generate_protocol_guidance(
        self, 
        user_input: str, 
        chat_history: List[Dict[str, str]],
        adler_persona: str
    ) -> Dict[str, Any]:
        
        # 세션 상태 업데이트 (대화 횟수만 업데이트)
        self.update_session(chat_history)
        
        # LLM을 사용하여 적절한 상담 단계 선택
        selected_stage = await self.select_stage_with_llm(user_input, chat_history)
        self.session.current_stage = selected_stage
        
        # 프로토콜 선택
        protocol_type = self.select_protocol(user_input, chat_history)
        self.session.protocol_type = protocol_type
        
        # 심각도 평가
        severity = self.assess_severity(user_input, chat_history)
        self.session.severity_level = severity
        
        # 현재 단계 가이드라인
        stage_guideline = self.get_stage_guideline(self.session.current_stage)
        
        # 통합 프롬프트 생성
        protocol_prompt = self._build_integrated_prompt(
            adler_persona=adler_persona,
            protocol_type=protocol_type,
            stage_guideline=stage_guideline,
            severity=severity,
            stage=self.session.current_stage
        )
        
        return {
            "protocol_prompt": protocol_prompt,
            "protocol_type": protocol_type.value,
            "current_stage": self.session.current_stage.value,
            "severity_level": severity,
            "stage_guideline": stage_guideline,
            "session_state": self.session.to_dict()
        }
    
    # 통합 프로토콜 프롬프트 구성
    def _build_integrated_prompt(
        self,
        adler_persona: str,
        protocol_type: ProtocolType,
        stage_guideline: Dict[str, str],
        severity: str,
        stage: TherapyStage
    ) -> str:
        
        # 기본 아들러 페르소나
        prompt_parts = [adler_persona]
        
        # 현재 상담 단계 가이드라인 추가
        stage_section = f"""

[현재 상담 단계: {stage_guideline.get('focus', '')}]
- 지침: {stage_guideline.get('guideline', '')}
- 심각도 수준: {severity}
"""
        prompt_parts.append(stage_section)
        
        # 위기 상황 대응
        if severity in ["critical", "high"]:
            crisis_guidance = """
[위기 개입 프로토콜]
- 즉각적인 안전 확보가 최우선입니다
- 전문 기관 연계를 고려하세요 (자살예방상담전화 1393, 정신건강위기상담 1577-0199)
- 구체적이고 실천 가능한 안전 계획을 제시하세요
"""
            prompt_parts.append(crisis_guidance)
        
        # 답변 구조 (재해석 단계 제거)
        answer_structure = """

[답변 구조 - 간결하게 작성]
1. 감정 인정 및 공감 (1문장):
   - 사용자의 감정을 있는 그대로 수용하고 공감합니다
   - 예: "힘드시는 마음 충분히 이해됩니다"
   - 예: "그런 마음이 드시는군요"

2. 현재 단계에 맞는 자연스러운 질문 또는 공감문 (1문장):
   - 단계별 지침에 따라 적절한 질문이나 공감을 제시합니다
   - 고정된 질문이 아니라 상황에 맞는 자연스러운 질문을 생성하세요
   - 구체적인 상황(예: 상사, 관계, 직장 문제)이 언급되면, 그에 대한 구체적이고 깊이 있는 질문을 하세요
   - 예시:
     * 감정 탐색: "어떤 부분이 가장 힘드신가요?" 또는 "구체적으로 어떤 상황이었는지 말씀해 주실 수 있을까요?"
     * 강점/자원 찾기: "이런 상황에서도 어떻게 버티고 계신 건가요?"
     * 해결 중심: "조금이라도 나아진다면 어떤 모습일까요?"
     * 행동 계획: "지금 할 수 있는 작은 것 하나는 무엇일까요?"

**절대 준수 사항**: 
- 반드시 1~2문장으로 매우 간결하게 작성
- 공감(1단계)은 필수입니다
- 재해석 단계는 포함하지 마세요
- 고정된 질문이 아니라 상황에 맞는 자연스러운 질문을 하세요
- 구체적인 상황이 언급되면 반드시 그 상황에 대해 더 자세히 탐색하는 질문을 포함하세요
- "언제든지 말씀해주세요", "더 이야기하고 싶으시면", "언제든 다시 찾아주세요" 같은 마무리/종료 표현은 절대 사용하지 마세요
- 상담을 계속 이어가도록 하는 질문을 반드시 포함하세요
- 사용자의 자율성과 주도성을 존중
- 불필요한 설명이나 예시를 추가하지 마세요
"""
        prompt_parts.append(answer_structure)
        
        return "\n".join(prompt_parts)