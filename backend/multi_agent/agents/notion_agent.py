"""
LangChain 최신 버전을 활용한 Notion Agent
RunnableConfig를 사용하여 컨텍스트 기반 Notion 작업 수행
"""
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# 1. 환경 설정
tools_path = Path(__file__).resolve().parent.parent.parent.parent / "tools"
if str(tools_path) not in sys.path:
    sys.path.insert(0, str(tools_path))

from tools import notion_tool
from .base_agent import BaseAgent
from app.core.config import settings

# LangChain 최신 버전 임포트
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent  # ✅ 최신 버전!
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, Field

# ------------------------------------------------------------------
# 4. 입력 스키마 정의
# ------------------------------------------------------------------
class SearchInput(BaseModel):
    query: str = Field(
        description=(
            "검색할 페이지 제목 또는 질문 내용. "
            "절대 요약/변경하지 말고 사용자가 말한 내용 전체를 그대로 넣어라."
        )
    )
    page_size: int = Field(default=10, description="결과 개수 (기본값: 10)")
    return_mode: str = Field(
        default="content",
        description=(
            "반환 모드: 'content' (페이지 전체 내용 마크다운 반환) 또는 "
            "'answer' (페이지 내용 기반으로 질문에 답변). "
            "사용자가 '내용 보여줘', '전체 내용' 같은 요청을 하면 'content', "
            "'~에 대해 설명해줘', '~이 뭐야' 같은 질문을 하면 'answer'를 사용하세요."
        )
    )


class CreatePageInput(BaseModel):
    """페이지 생성 입력 스키마"""
    parent_page_name: str = Field(description="상위 페이지 이름 또는 ID (이 페이지 하위에 새 페이지 생성)")
    title: str = Field(
        description=(
            "새로 생성할 페이지의 제목. "
            "**중요**: 이 제목으로 기존 페이지를 검색하지 않고 바로 새 페이지를 생성합니다. "
            "제목 중복 여부를 확인하지 않으며, 무조건 새 페이지를 만듭니다."
        )
    )
    content: str = Field(description="페이지 내용 (Markdown 형식, 선택적)", default="")


# ------------------------------------------------------------------
# 5. LangChain Tools (최신 패턴)
# ------------------------------------------------------------------
# RunnableConfig를 사용하여 user_id에 접근
# config 파라미터는 LLM에 노출되지 않으며 자동으로 주입됩니다.

@tool("search_notion", args_schema=SearchInput)
async def search_notion_tool(
    query: str,
    config: RunnableConfig,
    page_size: int = 10,
    return_mode: str = "content",
) -> str:
    """
    Notion의 실제 검색 API(notion.search)를 사용하여 페이지를 검색합니다.
    
    두 가지 모드:
    1. 'content': 검색된 페이지들의 전체 내용을 마크다운 형식으로 반환합니다.
    2. 'answer': 검색된 페이지 내용을 기반으로 사용자의 질문에 대해 답변을 생성합니다.
    
    Args:
        query: 검색할 페이지 제목 또는 질문 내용
        page_size: 결과 개수 (기본값: 3)
        return_mode: 'content' (전체 내용 반환) 또는 'answer' (질문에 답변)
    """
    print("=" * 80)
    print("🔧 [search_notion_tool] 도구 호출됨!")
    print(f"  Query: {query}")
    print(f"  Page Size: {page_size}")
    print(f"  Return Mode: {return_mode}")
    print(f"  Config 존재: {config is not None}")
    print("=" * 80)

    # 1) config에서 user_id 꺼내기
    user_id = None
    if config and getattr(config, "configurable", None):
        user_id = config.configurable.get("user_id")
    elif config:
        # dict 형태일 수도 있으므로 fallback
        user_id = config.get("configurable", {}).get("user_id") if isinstance(config, dict) else None
    
    if not user_id:
        return "오류: 사용자 정보(user_id)를 찾을 수 없습니다."

    # 2) Notion의 실제 search API 호출
    search_result = await notion_tool.search_pages(user_id, query, page_size=page_size)
    
    if not search_result["success"]:
        error_msg = f"검색 중 오류가 발생했습니다: {search_result.get('error', '알 수 없는 오류')}"
        print(f"❌ [search_notion_tool] {error_msg}")
        return error_msg
    
    found_pages = search_result["data"]["pages"]
    
    # 3) 페이지 제목이 쿼리에 포함되는 페이지 찾기 (유연한 매칭)
    # 쿼리(긴 문장) 안에 페이지 제목(짧은 단어/구문)이 들어있으면 매칭
    q_normalized = (query or "").strip().lower().replace(" ", "").replace("　", "")
    
    matched_page = None
    longest_match_length = 0  # 가장 긴 제목을 우선 선택 (더 구체적인 매칭)
    
    for page in found_pages:
        title = (page.get("title") or "").strip()
        if not title:
            continue
        
        title_normalized = title.lower().replace(" ", "").replace("　", "")
        
        # 페이지 제목이 쿼리 안에 포함되는지 확인 (포함 관계)
        if title_normalized in q_normalized:
            # 더 긴 제목을 우선 선택 (더 구체적인 매칭)
            if len(title_normalized) > longest_match_length:
                matched_page = page
                longest_match_length = len(title_normalized)
                print(f"✅ [search_notion_tool] 매칭되는 페이지 발견: '{title}' (ID: {page.get('id')}) - 제목이 쿼리에 포함됨")
    
    # 매칭되는 페이지가 없는 경우
    if not matched_page:
        print(f"⚠️ [search_notion_tool] 정확히 일치하는 페이지를 찾을 수 없습니다. 검색 결과: {len(found_pages)}개")
        for idx, page in enumerate(found_pages, 1):
            print(f"  [{idx}] 제목: '{page.get('title', '제목 없음')}' (ID: {page.get('id', 'N/A')})")
        
        # 전체 인덱스에서 키워드가 포함된 페이지 찾기
        all_pages = await notion_tool.get_or_build_page_index(user_id)
        q_lower = (query or "").strip().lower()
        
        keyword_matches = []
        for p in all_pages:
            title = (p.get("title") or "").lower()
            if not title:
                continue
            
            title_normalized = title.replace(" ", "").replace("　", "")
            
            # 키워드가 제목에 포함되어 있는지 확인
            if (q_lower in title or q_normalized in title_normalized or 
                any(word in title for word in q_lower.split() if len(word) > 1)):
                keyword_matches.append(p)
        
        if keyword_matches:
            # 키워드가 있는 페이지 목록 반환 (최대 10개)
            keyword_matches = keyword_matches[:10]
            page_list = "\n".join([f"- {p.get('title', '제목 없음')}" for p in keyword_matches])
            
            msg = f'"{query}"와 관련된 페이지를 찾을 수 없습니다.\n\n다음과 같은 키워드가 포함된 페이지들을 찾았습니다. 정확한 페이지 제목을 입력해주세요:\n\n{page_list}'
            print(f"⚠️ [search_notion_tool] 키워드 매칭 페이지 {len(keyword_matches)}개 반환")
            return msg
        else:
            msg = f'"{query}"와(과) 관련된 페이지를 찾을 수 없습니다.'
            print(f"⚠️ [search_notion_tool] {msg}")
            return msg

    # 4) 매칭되는 페이지의 내용만 가져오기 (순회하지 않음)
    all_contents = []
    page_id = matched_page["id"]
    title = matched_page.get("title") or "제목 없음"
    print(f"  📄 페이지 '{title}' 내용 가져오는 중... (id={page_id})")

    content_res = await notion_tool.get_page_content(user_id, page_id)
    if not content_res.get("success"):
        error_msg = f'페이지 내용 조회 실패: {content_res.get("error")}'
        print(f"  ⚠️ {error_msg}")
        return error_msg

    # 전체 마크다운 내용 가져오기
    md = content_res["data"]["markdown"]
    
    # 하위 페이지만 있는지 확인 (get_page_content에서 반환하는 메타데이터 사용)
    is_only_pages = content_res["data"].get("is_only_child_pages", False)
    
    if is_only_pages:
        # 하위 페이지만 있는 경우, 제목만 반환
        print(f"  ℹ️ 페이지 '{title}'는 하위 페이지만 포함되어 있습니다. 제목만 반환합니다.")
        all_contents.append({
            "title": title,
            "content": None,  # 하위 페이지만 있음을 표시
            "is_page_list_only": True
        })
    else:
        all_contents.append({
            "title": title,
            "content": md,
            "is_page_list_only": False
        })

    if not all_contents:
        return f'"{query}"와(과) 매칭되는 페이지의 내용을 불러오지 못했습니다.'

    # 5) return_mode에 따라 처리
    if return_mode == "answer":
        # 페이지 내용을 기반으로 질문에 답변 생성
        # 하위 페이지만 있는 페이지는 제외하고 실제 내용이 있는 페이지만 사용
        pages_with_content = [item for item in all_contents if not item.get("is_page_list_only")]
        
        if not pages_with_content:
            # 모든 페이지가 하위 페이지만 있는 경우
            page_titles = [item["title"] for item in all_contents]
            return f'검색된 페이지들({", ".join(page_titles)})은 하위 페이지만 포함되어 있어 실제 내용이 없습니다. 구체적인 하위 페이지 제목으로 검색해주세요.'
        
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
        )
        
        # 실제 내용이 있는 페이지들만 컨텍스트로 합치기
        context_parts = []
        for item in pages_with_content:
            context_parts.append(f"## {item['title']}\n\n{item['content']}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        print(f"  🤖 LLM을 사용하여 답변 생성 중... (컨텍스트 길이: {len(context)} 문자)")
        
        # 질문에 답변하는 프롬프트
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 Notion 페이지 내용을 기반으로 정확하게 답변하는 AI 어시스턴트입니다.

다음 규칙을 엄격히 준수하여 답변하세요:

1. **답변 원칙**:
   - 제공된 Notion 페이지 내용(Context)에 있는 내용만으로 답변하세요.
   - 사용자가 묻는 정보가 페이지에 명확히 없더라도, 문맥상 유추할 수 있거나 관련된 내용이 있다면 이를 **페이지 내에서 찾아서** 설명해 주세요.
   - 아예 관련 내용이 없을 때만 "죄송합니다. 관련 정보를 Notion 페이지에서 찾을 수 없습니다."라고 답변하세요.

2. **Markdown 필수**: 가독성을 위해 Markdown을 적극 활용하세요.
   - 모든 목록(글머리 기호)과 소제목(`###`) 앞뒤에는 반드시 줄바꿈 문자를 두 번 사용하여 빈 줄을 만드세요.
   - 핵심 내용은 **볼드체**로 강조합니다.

3. **간결성**: 불필요한 서론을 빼고 핵심만 간결하게 답변하세요.
4. **언어**: 한국어로 답변하세요."""),
            ("user", """다음 Notion 페이지 내용을 참고하여 질문에 답변해주세요.
            
{context}

질문: {question}

답변:""")
        ])
        
        chain = prompt | llm
        
        try:
            answer = await chain.ainvoke({
                "context": context,
                "question": query
            })
            
            result_text = answer.content if hasattr(answer, 'content') else str(answer)
            print(f"✅ [search_notion_tool] 답변 생성 완료 (길이: {len(result_text)} 문자)")
            return result_text
        except Exception as e:
            error_msg = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
            print(f"❌ [search_notion_tool] {error_msg}")
            import traceback
            traceback.print_exc()
            return error_msg
    
    else:  # return_mode == "content"
        # 페이지 전체 내용을 마크다운 형태로 반환
        summary_parts = []
        for item in all_contents:
            if item.get("is_page_list_only"):
                # 하위 페이지만 있는 경우, 제목만 표시
                block = f"## {item['title']}\n\n이 페이지는 하위 페이지만 포함되어 있습니다.\n\n---\n"
            else:
                block = f"## {item['title']}\n\n{item['content']}\n\n---\n"
            summary_parts.append(block)

        result_text = "\n".join(summary_parts)
        print(f"✅ [search_notion_tool] 전체 내용 반환 (총 {len(summary_parts)}개 페이지, 길이: {len(result_text)} 문자)")
    return result_text


@tool("create_page", args_schema=CreatePageInput)
async def create_page_tool(
    parent_page_name: str,
    title: str,
    config: RunnableConfig,
    content: str = "",
) -> str:
    """
    Notion(노션)에 새 페이지를 생성합니다.
    
    **중요**: 이 도구는 새 페이지를 생성하는 것이며, title로 기존 페이지를 검색하지 않습니다.
    title은 생성할 새 페이지의 제목이며, 무조건 새 페이지로 생성됩니다.
    
    Args:
        parent_page_name: 상위 페이지 이름 또는 ID (이 페이지를 찾아서 하위에 생성)
        title: 새로 생성할 페이지 제목
        content: 페이지 내용 (Markdown 형식)
        config: RunnableConfig (자동 주입, LLM에 노출되지 않음)
    
    Returns:
        생성된 페이지 제목 또는 오류 메시지
    """
    print("=" * 80)
    print("🔧 [create_page_tool] 도구 호출됨!")
    print(f"  Parent Page: {parent_page_name}")
    print(f"  Title: {title}")
    print(f"  Content 길이: {len(content)} 문자")
    print(f"  Config 존재: {config is not None}")
    if config:
        user_id = config.get("configurable", {}).get("user_id")
        print(f"  User ID: {user_id}")
    print("=" * 80)
    
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        error_msg = "오류: 사용자 인증 정보를 찾을 수 없습니다."
        print(f"❌ [create_page_tool] {error_msg}")
        return error_msg
    
    # parent_page_name이 ID인지 확인 (UUID 형식)
    import re
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
    
    if uuid_pattern.match(parent_page_name):
        # ID로 직접 사용
        parent_id = parent_page_name
    else:
        # 이름으로 검색
        search_res = await notion_tool.search_pages(user_id, parent_page_name, page_size=1)
        if not search_res["success"] or not search_res["data"]["pages"]:
            return f"오류: 상위 페이지 '{parent_page_name}'를 찾을 수 없습니다."
        parent_id = search_res["data"]["pages"][0]["id"]
    
    # 페이지 생성
    if content:
        res = await notion_tool.create_page_from_markdown(user_id, parent_id, title, content)
    else:
        res = await notion_tool.create_page(user_id, parent_id, title)
    
    if res["success"]:
        result_text = f"✅ 페이지가 성공적으로 생성되었습니다!\nURL: {res['data']['url']}"
        print(f"✅ [create_page_tool] 페이지 생성 성공: {res['data']['url']}")
        return result_text
    else:
        error_msg = f"❌ 페이지 생성 실패: {res['error']}"
        print(f"❌ [create_page_tool] {error_msg}")
        return error_msg


# ------------------------------------------------------------------
# 6. NotionAgent 클래스
# ------------------------------------------------------------------
class NotionAgent(BaseAgent):
    """LangChain 최신 버전을 사용한 Notion Agent"""

    def __init__(self) -> None:
        super().__init__(name="notion_agent", description="Notion 비서")

        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
        )

        self.tools = [
            search_notion_tool,
            create_page_tool,
        ]

        print("=" * 80)
        print("🔧 [NotionAgent.__init__] 등록된 도구 목록:")
        for i, tool in enumerate(self.tools, 1):
            print(f"  {i}. {tool.name}")
            print(f"     설명: {tool.description[:100]}...")
            if hasattr(tool, "args_schema"):
                print(f"     스키마: {tool.args_schema.__name__}")
        print("=" * 80)

        system_prompt = """
당신은 사용자의 Notion 워크스페이스에만 접근할 수 있는 Notion 전용 AI 비서입니다.

[사용 가능한 도구]
- search_notion: Notion의 실제 검색 API를 사용하여 페이지를 검색합니다. 두 가지 모드가 있습니다:
  * 'content' 모드: 검색된 페이지의 전체 내용을 마크다운 형식으로 반환합니다.
  * 'answer' 모드: 검색된 페이지 내용을 기반으로 사용자의 질문에 대해 답변을 생성합니다.
- create_page: Notion에 새 페이지를 생성합니다. parent_page_name으로 상위 페이지를 찾고, title로 새 페이지를 생성합니다.

[핵심 규칙]
1. **사용자 의도 파악 우선**:
   - 사용자가 **행동 동사**를 사용하면 → **create_page 도구를 사용**하세요.
   - 사용자가 **질문 동사**를 사용하면 → **search_notion 도구를 사용**하세요.

2. **create_page 사용 시**:
     * parent_page_name: 사용자가 명시적으로 언급한 상위 페이지 이름.
     * title: 저장할 내용을 요약한 제목을 생성하세요. 사용자가 제목을 명시했다면 그대로 사용하세요.
     * content: 사용자가 언급한 내용을 마크다운 형식으로 작성하세요.
   - 사용자가 "이 대화", "방금 답변", "위 내용"," 이 내용" 등을 언급하면, 이는 이전 대화나 특정 내용을 참조하는 것입니다.

3. **중요: 도구 실행 후 즉시 종료**:
   - 도구를 한 번 실행한 후에는 반드시 최종 답변을 생성하고 종료하세요.
   - 같은 도구를 여러 번 호출하지 마세요.
   - 도구 실행 결과를 받으면 그 결과를 사용자에게 명확하게 전달하고 종료하세요.
   - 불필요한 추가 작업이나 반복 호출을 하지 마세요.
"""

        print("=" * 80)
        print("📝 [NotionAgent.__init__] 시스템 프롬프트:")
        print(system_prompt)
        print("=" * 80)
        
        llm_with_tools = self.llm.bind_tools(
            self.tools,
            tool_choice="any",
        )

        # LangGraph의 create_react_agent 사용 (supervisor.py와 동일한 방식)
        agent = create_react_agent(
            model=llm_with_tools,
            tools=self.tools,
            prompt=system_prompt,  # system message
        )

        self.agent = agent

    async def process(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Notion Agent를 실행합니다. (Stateless)
        
        Args:
            query: 사용자 질문
            user_id: 사용자 ID
            session_id: 세션 ID (로깅용)
            context: 추가 컨텍스트 (선택적)
        """
        try:
            print("=" * 80)
            print(f"🤖 [NotionAgent.process] 시작 (Stateless)")
            print(f"  Query: {query}")
            print(f"  User ID: {user_id}")
            print("=" * 80)
            
            final_answer = ""
            tool_result_received = False  # ToolMessage 수신 여부 추적
            should_stop = False  # 종료 플래그
            
            # 🔹 user_id를 configurable로 넘겨야 search_notion_tool에서 읽을 수 있음
            # recursion_limit 설정 (최대 10회로 제한)
            async for event in self.agent.astream(
                {"messages": [HumanMessage(content=query)]},
                config={
                    "configurable": {
                        "user_id": str(user_id),
                        "recursion_limit": 10,  # 최대 10회 반복 제한
                    }
                },
            ):
                if should_stop:
                    break
                    
                # event는 노드 이름을 키로 하는 딕셔너리 (예: {'agent': {'messages': [...]}})
                for node_name, node_output in event.items():
                    if should_stop:
                        break
                        
                    # node_output에서 messages 추출
                    messages = []
                    if isinstance(node_output, dict):
                        messages = node_output.get("messages", [])
                    elif isinstance(node_output, list):
                        messages = node_output
                    
                    for msg in messages:
                        if should_stop:
                            break
                            
                        # ToolMessage를 받으면 즉시 결과 추출하고 종료
                        if isinstance(msg, ToolMessage):
                            tool_result = msg.content
                            print(f"📦 [NotionAgent] ToolMessage 받음 - 길이: {len(str(tool_result))}, 내용: {str(tool_result)[:200]}")
                            final_answer = tool_result
                            tool_result_received = True
                            should_stop = True
                            break
                        
                        # AIMessage에서 최종 답변 추출 (ToolMessage가 없는 경우)
                        if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                            # tool_calls가 없는 경우만 최종 답변으로 간주
                            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                                if not tool_result_received:  # ToolMessage를 받지 않은 경우에만
                                    final_answer += msg.content
                    
                    if should_stop:
                        break
                
                if should_stop:
                    break

            # ToolMessage를 받지 못했고 final_answer가 비어있는 경우
            if not final_answer:
                final_answer = "응답을 생성할 수 없습니다."
            
            return {
                "success": True,
                "answer": final_answer,
                "agent_used": self.name,
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "answer": f"오류가 발생했습니다: {str(e)}",
                "agent_used": self.name
            }
            