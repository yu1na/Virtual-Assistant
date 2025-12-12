"""
Multi-Agent 시스템 테스트 스크립트

각 에이전트와 Supervisor를 테스트합니다.
"""

import asyncio
import sys
from pathlib import Path

# 경로 설정
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from multi_agent.supervisor import SupervisorAgent
from multi_agent.schemas import MultiAgentRequest


async def test_supervisor():
    """Supervisor Agent 테스트"""
    print("=" * 60)
    print("Multi-Agent 시스템 테스트")
    print("=" * 60)
    
    # Supervisor 초기화
    print("\n1️⃣ Supervisor Agent 초기화 중...")
    supervisor = SupervisorAgent()
    
    # 테스트 질문들
    test_queries = [
        "안녕하세요!",  # Chatbot
        "연차 규정이 어떻게 돼?",  # RAG
        "새로운 마케팅 아이디어를 내고 싶어",  # Brainstorming
        "오늘 할 일을 정리해줘",  # Planner
        "이번 주 실적을 분석해줘",  # Report
        "스트레스가 많아서 힘들어",  # Therapy
    ]
    
    print("\n2️⃣ 테스트 질문 실행\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─' * 60}")
        print(f"질문 {i}: {query}")
        print(f"{'─' * 60}")
        
        try:
            # 요청 생성
            request = MultiAgentRequest(
                query=query,
                session_id=f"test-session-{i}"
            )
            
            # Supervisor 실행
            response = await supervisor.process(request)
            
            # 결과 출력
            print(f"\n✅ 사용된 에이전트: {response.agent_used}")
            print(f"⏱️  처리 시간: {response.processing_time:.2f}초")
            print(f"\n📝 응답:\n{response.answer}")
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)


async def test_available_agents():
    """사용 가능한 에이전트 목록 테스트"""
    print("\n3️⃣ 사용 가능한 에이전트 목록\n")
    
    supervisor = SupervisorAgent()
    agents = supervisor.get_available_agents()
    
    for agent in agents:
        print(f"\n📌 {agent['name']}")
        print(f"   설명: {agent['description']}")


async def main():
    """메인 테스트 함수"""
    try:
        await test_supervisor()
        await test_available_agents()
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트 중단됨")
    except Exception as e:
        print(f"\n\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 환경 변수 확인
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일을 확인하거나 환경 변수를 설정하세요.")
        sys.exit(1)
    
    # 테스트 실행
    asyncio.run(main())

