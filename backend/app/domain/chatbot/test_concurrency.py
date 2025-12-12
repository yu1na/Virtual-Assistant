"""
Chatbot SessionManager 동시성 테스트

여러 스레드가 동시에 세션을 생성하고 메시지를 추가하는 상황을 시뮬레이션합니다.
Race condition, 데이터 무결성, 성능을 검증합니다.
"""

import threading
import time
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from app.domain.chatbot.session_manager import SessionManager


def test_concurrent_session_creation():
    """
    테스트 1: 동시 세션 생성
    - 100개 스레드가 동시에 세션 생성
    - 세션 ID 중복 없어야 함
    """
    print("\n" + "="*60)
    print("📋 테스트 1: 동시 세션 생성 (100개 스레드)")
    print("="*60)
    
    session_manager = SessionManager()
    session_ids = []
    errors = []
    lock = threading.Lock()
    
    def create_session():
        try:
            session_id = session_manager.create_session()
            with lock:
                session_ids.append(session_id)
        except Exception as e:
            with lock:
                errors.append(str(e))
    
    # 100개 스레드 동시 실행
    threads = [threading.Thread(target=create_session) for _ in range(100)]
    
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    end = time.time()
    
    # 결과 검증
    unique_sessions = set(session_ids)
    
    print(f"✅ 완료 시간: {end - start:.3f}초")
    print(f"✅ 생성된 세션 수: {len(session_ids)}")
    print(f"✅ 고유 세션 수: {len(unique_sessions)}")
    print(f"✅ 오류 수: {len(errors)}")
    
    # 중복 체크
    if len(session_ids) == len(unique_sessions) == 100:
        print("✅ 성공: 세션 ID 중복 없음!")
        return True
    else:
        print(f"❌ 실패: 세션 ID 중복 또는 누락 발생!")
        if errors:
            print(f"   오류: {errors[:3]}")
        return False


def test_concurrent_message_addition():
    """
    테스트 2: 동시 메시지 추가
    - 10개 세션에 각각 50개 스레드가 메시지 추가
    - 메시지 개수가 정확해야 함
    """
    print("\n" + "="*60)
    print("📋 테스트 2: 동시 메시지 추가 (10 세션 × 50 메시지)")
    print("="*60)
    
    session_manager = SessionManager()
    
    # 10개 세션 생성
    session_ids = [session_manager.create_session() for _ in range(10)]
    errors = []
    lock = threading.Lock()
    
    def add_messages(session_id, count):
        """한 세션에 여러 메시지 추가"""
        try:
            for i in range(count):
                session_manager.add_message(
                    session_id,
                    "user" if i % 2 == 0 else "assistant",
                    f"메시지 {i}"
                )
                time.sleep(0.001)  # 실제 네트워크 지연 시뮬레이션
        except Exception as e:
            with lock:
                errors.append(f"{session_id}: {str(e)}")
    
    # 각 세션마다 50개 스레드가 동시에 메시지 추가
    threads = []
    for session_id in session_ids:
        for _ in range(50):
            t = threading.Thread(target=add_messages, args=(session_id, 1))
            threads.append(t)
    
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    end = time.time()
    
    # 결과 검증
    print(f"✅ 완료 시간: {end - start:.3f}초")
    print(f"✅ 총 스레드 수: {len(threads)}")
    print(f"✅ 오류 수: {len(errors)}")
    
    # 각 세션의 메시지 개수 확인
    all_correct = True
    for session_id in session_ids:
        history = session_manager.get_history(session_id)
        expected = min(50, 15)  # max_history가 15이므로
        actual = len(history)
        
        if actual != expected:
            print(f"❌ 세션 {session_id[:8]}: 예상 {expected}개, 실제 {actual}개")
            all_correct = False
    
    if all_correct and len(errors) == 0:
        print("✅ 성공: 모든 세션의 메시지 개수 정확!")
        print(f"   (각 세션당 15개 메시지 - max_history 제한)")
        return True
    else:
        print(f"❌ 실패: 메시지 누락 또는 오류 발생!")
        if errors:
            print(f"   오류: {errors[:3]}")
        return False


def test_concurrent_mixed_operations():
    """
    테스트 3: 혼합 작업 (생성 + 읽기 + 쓰기 + 삭제)
    - 실제 서버 환경과 유사한 복잡한 시나리오
    """
    print("\n" + "="*60)
    print("📋 테스트 3: 혼합 작업 (생성/읽기/쓰기/삭제 동시 실행)")
    print("="*60)
    
    session_manager = SessionManager()
    session_ids = []
    errors = []
    lock = threading.Lock()
    
    def worker(worker_id):
        """실제 사용자 시뮬레이션"""
        try:
            # 세션 생성
            session_id = session_manager.create_session()
            with lock:
                session_ids.append(session_id)
            
            # 메시지 추가
            for i in range(5):
                session_manager.add_message(
                    session_id,
                    "user" if i % 2 == 0 else "assistant",
                    f"Worker {worker_id} - Message {i}"
                )
            
            # 히스토리 읽기
            history = session_manager.get_history(session_id)
            assert len(history) == 5, f"메시지 개수 불일치: {len(history)}"
            
            # 세션 정보 조회
            info = session_manager.get_session_info(session_id)
            assert info is not None, "세션 정보 없음"
            
            # 일부 세션 삭제 (50% 확률)
            if worker_id % 2 == 0:
                session_manager.delete_session(session_id)
                
        except Exception as e:
            with lock:
                errors.append(f"Worker {worker_id}: {str(e)}")
    
    # 50명의 사용자 시뮬레이션
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    end = time.time()
    
    # 결과 검증
    remaining_sessions = session_manager.list_sessions()
    
    print(f"✅ 완료 시간: {end - start:.3f}초")
    print(f"✅ 생성된 세션 수: {len(session_ids)}")
    print(f"✅ 남은 세션 수: {len(remaining_sessions)}")
    print(f"✅ 오류 수: {len(errors)}")
    
    if len(errors) == 0 and len(session_ids) == 50:
        print("✅ 성공: 모든 작업 정상 완료!")
        print(f"   (삭제된 세션: 약 {50 - len(remaining_sessions)}개)")
        return True
    else:
        print(f"❌ 실패: 오류 발생!")
        if errors:
            print(f"   오류: {errors[:3]}")
        return False


def test_performance_benchmark():
    """
    테스트 4: 성능 벤치마크
    - 대량 요청 처리 속도 측정
    """
    print("\n" + "="*60)
    print("📋 테스트 4: 성능 벤치마크 (1000개 세션 × 10 메시지)")
    print("="*60)
    
    session_manager = SessionManager()
    
    def worker(worker_id):
        """세션 생성 + 메시지 10개 추가"""
        session_id = session_manager.create_session()
        for i in range(10):
            session_manager.add_message(
                session_id,
                "user" if i % 2 == 0 else "assistant",
                f"Message {i}"
            )
    
    # 1000명의 사용자 동시 접속
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(1000)]
    
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    end = time.time()
    
    total_time = end - start
    ops_per_sec = (1000 * 11) / total_time  # 11 operations per thread
    
    print(f"✅ 완료 시간: {total_time:.3f}초")
    print(f"✅ 총 작업 수: {1000 * 11:,}개")
    print(f"✅ 처리량: {ops_per_sec:,.0f} ops/sec")
    print(f"✅ 평균 응답 시간: {(total_time / 1000) * 1000:.2f}ms")
    
    # 성능 기준: 1000명이 10초 이내에 처리되어야 함
    if total_time < 10.0:
        print(f"✅ 성공: 성능 기준 통과! ({total_time:.2f}초 < 10초)")
        return True
    else:
        print(f"⚠️  경고: 성능 기준 미달 ({total_time:.2f}초 > 10초)")
        return False


def main():
    """모든 테스트 실행"""
    print("\n🚀 Chatbot SessionManager 동시성 테스트 시작")
    print("="*60)
    
    results = []
    
    # 테스트 실행
    results.append(("동시 세션 생성", test_concurrent_session_creation()))
    results.append(("동시 메시지 추가", test_concurrent_message_addition()))
    results.append(("혼합 작업", test_concurrent_mixed_operations()))
    results.append(("성능 벤치마크", test_performance_benchmark()))
    
    # 최종 결과
    print("\n" + "="*60)
    print("📊 최종 결과")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(results, key=lambda x: x[1])
    
    print("\n" + "="*60)
    print(f"🎯 전체: {passed}/{total} 테스트 통과")
    print("="*60)
    
    if passed == total:
        print("✅ 모든 동시성 테스트 통과! 🎉")
        return 0
    else:
        print("❌ 일부 테스트 실패")
        return 1


if __name__ == "__main__":
    exit(main())

