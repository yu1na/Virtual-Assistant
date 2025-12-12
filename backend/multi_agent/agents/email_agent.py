import sys
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

# Tools 경로 추가
tools_path = Path(__file__).resolve().parent.parent.parent.parent / "tools"
if str(tools_path) not in sys.path:
    sys.path.insert(0, str(tools_path))

from tools import gmail_tool
from .base_agent import BaseAgent
from app.core.config import settings

# -------------------------------------------------------------------------
# 데이터 모델 정의
# -------------------------------------------------------------------------
class EmailAction(BaseModel):
    """이메일 작업 분석 결과"""
    intent: str = Field(description="작업 의도 (send, search, unknown)")
    recipient_email: Optional[str] = Field(default=None, description="받는 사람 이메일 주소")
    subject: Optional[str] = Field(default=None, description="메일 제목")
    body: Optional[str] = Field(default=None, description="메일 본문 내용")
    search_query: Optional[str] = Field(default=None, description="메일 검색어 (보낸사람, 제목 등)")
    attachment_path: Optional[str] = Field(default=None, description="첨부할 파일의 경로 (보고서 PDF 등)")

# -------------------------------------------------------------------------
# Email Agent 클래스
# -------------------------------------------------------------------------
class EmailAgent(BaseAgent):
    """이메일 전송 및 검색을 담당하는 전문 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="email_agent",
            description="Gmail API를 사용하여 이메일을 전송하거나 검색합니다."
        )
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )

    async def process(self, query: Optional[str], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """이메일 작업 처리 메인 파이프라인"""
        print(f"\n📨 [Email Agent] 처리 시작: {query}")
        try:
            # 1. 사용자 ID 확인 (필수)
            user_id = context.get("user_id") if context else None
            print(f"   - User ID: {user_id}")
            
            if not user_id:
                print(f"❌ [Email Agent] User ID 없음")
                return {"success": False, "answer": "로그인이 필요한 기능입니다."}

            # 쿼리 정규화 및 기본값 적용
            normalized_query = (query or "").strip()
            if not normalized_query:
                # 검색어가 없을 때는 기본값으로 안 읽은 메일 조회
                print("   - 검색어 없음 → 기본 검색어 'is:unread' 적용")
                action = EmailAction(intent="search", search_query="is:unread")
            else:
                # 2. 의도 및 정보 분석
                print(f"   - LLM 분석 시작...")
                action = await self._analyze_request(normalized_query, context)
                print(f"✅ [Email Agent] 분석 완료: {action}")
            
            # 3. 작업 수행
            if action.intent == "send":
                print(f"🚀 [Email Agent] 메일 전송 실행")
                return await self._send_email(action, user_id)
            elif action.intent == "search":
                print(f"🚀 [Email Agent] 메일 검색 실행")
                return await self._search_emails(action, user_id)
            else:
                print(f"⚠️ [Email Agent] 의도 파악 실패: {action.intent}")
                return {"success": False, "answer": "이메일 관련 작업을 이해하지 못했습니다. '메일 보내줘' 또는 '메일 찾아줘'와 같이 말씀해주세요.", "agent_used": self.name}

        except Exception as e:
            import traceback
            print(f"\n🔥 [Email Agent] 처리 중 오류 발생!")
            traceback.print_exc()
            return {"success": False, "answer": f"이메일 작업 중 오류 발생: {str(e)}", "agent_used": self.name}

    async def _analyze_request(self, query: str, context: Optional[Dict[str, Any]]) -> EmailAction:
        """사용자 요청 분석"""
        
        # 이전 대화나 컨텍스트에서 파일 경로가 있는지 힌트 제공
        context_hint = ""
        if context:
            if context.get("last_generated_file"):
                context_hint += f"\n[참고] 방금 생성된 파일 경로: {context['last_generated_file']}"
            if "conversation_history" in context:
                history = context["conversation_history"][-5:]
                context_hint += f"\n[참고] 대화 이력: {history}"

        parser = PydanticOutputParser(pydantic_object=EmailAction)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 이메일 관리 전문 비서입니다.
사용자의 요청을 분석하여 이메일 전송(send) 또는 검색(search) 정보를 추출하세요.

[규칙]
1. **send (전송)**:
   - recipient_email: 이메일 주소를 정확히 추출하세요. 없다면 null.
   - subject: 제목이 명시되지 않았다면 내용을 요약해서 생성하세요.
   - body: 본문 내용을 작성하세요. "아까 그 내용" 등을 말하면 대화 이력을 참고해 요약하세요.
   - attachment_path: "보고서 보내줘", "파일 첨부해줘" 등의 요청이 있고, **컨텍스트에 파일 경로가 있다면** 그 경로를 추출하세요.
2. **search (검색)**:
   - search_query: 검색할 키워드 (예: "is:unread", "from:someone@test.com")

{format_instructions}"""),
            ("user", "사용자 요청: {query}\n{context_hint}")
        ])

        chain = prompt | self.llm | parser
        return await chain.ainvoke({
            "format_instructions": parser.get_format_instructions(),
            "query": query,
            "context_hint": context_hint
        })

    async def _send_email(self, action: EmailAction, user_id: str) -> Dict[str, Any]:
        """이메일 전송 실행"""
        if not action.recipient_email:
            return {"success": False, "answer": "받는 사람의 이메일 주소를 알려주세요."}

        result = await gmail_tool.send_email(
            user_id=str(user_id),
            to=action.recipient_email,
            subject=action.subject or "제목 없음",
            body=action.body or "",
            attachment_path=action.attachment_path 
        )

        if result["success"]:
            msg = f"✅ **{action.recipient_email}**님에게 메일을 보냈습니다!"
            if action.attachment_path:
                filename = Path(action.attachment_path).name
                msg += f"\n📎 첨부파일: `{filename}`"
            return {"success": True, "answer": msg, "agent_used": self.name}
        else:
            # [수정] 에러 메시지가 '토큰' 관련이면 친절하게 안내
            error_msg = result['error']
            if "토큰을 찾을 수 없습니다" in error_msg:
                return {
                    "success": False, 
                    "answer": "📧 이 기능을 사용하려면 **Google 계정 연동**이 필요합니다.\n로그아웃 후 **Google로 로그인**하거나 계정을 연동해 주세요.", 
                    "agent_used": self.name
                }
            
            return {"success": False, "answer": f"메일 전송 실패: {error_msg}", "agent_used": self.name}

    async def _search_emails(self, action: EmailAction, user_id: str) -> Dict[str, Any]:
        """이메일 검색 실행"""
        query = action.search_query or "is:unread"
        result = await gmail_tool.list_messages(str(user_id), query=query, max_results=5)

        if result["success"]:
            msgs = result["data"]["messages"]
            if not msgs:
                return {"success": True, "answer": "검색된 메일이 없습니다.", "agent_used": self.name}
            
            answer = f"🔍 **'{query}'** 검색 결과입니다:\n"
            for msg in msgs:
                answer += f"- **[{msg['subject']}]** (보낸이: {msg['from']})\n"
            return {"success": True, "answer": answer, "agent_used": self.name}
        else:
            return {"success": False, "answer": f"메일 검색 실패: {result['error']}", "agent_used": self.name}