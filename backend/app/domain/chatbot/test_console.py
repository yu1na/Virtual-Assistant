"""
채팅봇 콘솔 테스트

터미널에서 대화형으로 챗봇을 테스트합니다.
- 세션 생성 및 대화 히스토리 유지 확인
- OpenAI API 연동 확인
- 명령어: /new (새 세션), /history (히스토리 보기), /info (세션 정보), /exit (종료)
"""

import sys
import os
import time
from pathlib import Path

# 한글 입력 처리 개선 (readline 모듈)
try:
    import readline  # Mac/Linux에서 한글 백스페이스 처리 개선
except ImportError:
    pass  # Windows는 readline이 없지만 기본 input()이 더 잘 작동

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.domain.chatbot.service import ChatService

# 입력 버퍼 플러시용
try:
    import termios
    TERMIOS_AVAILABLE = True
except ImportError:
    TERMIOS_AVAILABLE = False

# 환경 변수 로드
load_dotenv()


def flush_input_buffer():
    """입력 버퍼 플러시 (한글 입력 문제 해결)"""
    if TERMIOS_AVAILABLE:
        try:
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except:
            pass
    
    # 짧은 대기로 버퍼 안정화
    time.sleep(0.05)


def print_header():
    """헤더 출력"""
    print("\n" + "=" * 60)
    print("🤖 채팅봇 콘솔 테스트")
    print("=" * 60)
    print("\n명령어:")
    print("  /new      - 새로운 세션 시작")
    print("  /history  - 대화 히스토리 보기")
    print("  /info     - 세션 정보 보기")
    print("  /exit     - 종료")
    print("\n" + "-" * 60 + "\n")


def print_message(role: str, content: str):
    """메시지 출력"""
    if role == "user":
        print(f"\n👤 사용자: {content}")
    elif role == "assistant":
        print(f"\n🤖 AI 비서: {content}")
    else:
        print(f"\n{content}")


def print_history(chat_service: ChatService, session_id: str):
    """대화 히스토리 출력"""
    history = chat_service.get_session_history(session_id)
    
    if not history:
        print("\n📭 대화 히스토리가 없습니다.")
        return
    
    print("\n" + "=" * 60)
    print(f"📜 대화 히스토리 (총 {len(history)}개)")
    print("=" * 60)
    
    for i, msg in enumerate(history, 1):
        role_icon = "👤" if msg["role"] == "user" else "🤖"
        print(f"\n[{i}] {role_icon} {msg['role'].upper()}")
        print(f"    {msg['content']}")
        print(f"    ⏰ {msg['timestamp']}")
    
    print("\n" + "=" * 60)


def print_session_info(chat_service: ChatService, session_id: str):
    """세션 정보 출력"""
    info = chat_service.get_session_info(session_id)
    
    if not info:
        print("\n❌ 세션 정보를 찾을 수 없습니다.")
        return
    
    print("\n" + "=" * 60)
    print("ℹ️  세션 정보")
    print("=" * 60)
    print(f"\n📝 세션 ID: {session_id}")
    print(f"🕐 생성 시간: {info['created_at']}")
    print(f"🕑 마지막 활동: {info['last_activity']}")
    print(f"💬 전체 메시지 수: {info['message_count']}")
    print(f"📊 현재 유지 중: {info['current_message_count']}개 (최대 20개)")
    print("\n" + "=" * 60)


def main():
    """메인 함수"""
    print_header()
    
    # 채팅 서비스 초기화
    try:
        chat_service = ChatService()
        max_history = chat_service.session_manager.max_history
        print("✅ 채팅 서비스 초기화 완료")
        print(f"📊 대화 히스토리 크기: {max_history}개 (최근 {max_history}개 메시지 유지)\n")
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        print("\n💡 OPENAI_API_KEY 환경 변수가 설정되어 있는지 확인하세요.")
        return
    
    # 세션 생성
    session_id = chat_service.create_session()
    print(f"✅ 새 세션 생성: {session_id}\n")
    print("💬 대화를 시작하세요! (명령어는 /help)\n")
    
    # 대화 루프
    while True:
        try:
            # 입력 버퍼 플러시 (이전 입력 잔여물 제거)
            flush_input_buffer()
            
            # 사용자 입력
            user_input = input("👤 사용자: ").strip()
            
            if not user_input:
                continue
            
            # 명령어 처리
            if user_input == "/exit":
                print("\n👋 채팅을 종료합니다. 안녕히 가세요!")
                break
            
            elif user_input == "/new":
                session_id = chat_service.create_session()
                print(f"\n✅ 새 세션 생성: {session_id}")
                print("💬 새로운 대화를 시작하세요!\n")
                flush_input_buffer()
                continue
            
            elif user_input == "/history":
                print_history(chat_service, session_id)
                flush_input_buffer()
                continue
            
            elif user_input == "/info":
                print_session_info(chat_service, session_id)
                flush_input_buffer()
                continue
            
            elif user_input == "/help":
                print_header()
                flush_input_buffer()
                continue
            
            # 일반 메시지 처리
            print("\n⏳ AI 비서가 생각 중입니다...")
            
            response = chat_service.process_message(session_id, user_input)
            print_message("assistant", response)
            
            # 응답 후 버퍼 플러시 (다음 입력 준비)
            flush_input_buffer()
        
        except KeyboardInterrupt:
            print("\n\n👋 Ctrl+C로 종료합니다. 안녕히 가세요!")
            break
        
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            print("💡 계속 진행하려면 메시지를 입력하세요.\n")


if __name__ == "__main__":
    main()

