/**
 * Chatbot API 전용 서비스
 * backend/app/domain/chatbot 모듈과 통신
 * Multi-Agent 시스템 지원 추가
 */


const API_BASE_URL = 'http://localhost:8000/api/v1';
const SESSION_KEY = 'chatbot_session_id';
const MULTI_AGENT_SESSION_KEY = 'multi_agent_session_id';

// JWT 토큰 저장
let accessToken = null;

/**
 * 챗봇 서비스 초기화 (토큰 설정)
 * @param {string} token - JWT 액세스 토큰
 */
export function initChatbotService(token) {
  accessToken = token;
  console.log('✅ 챗봇 서비스 - 액세스 토큰 설정 완료');
}

/**
 * 세션 ID 가져오기 (없으면 새로 생성)
 * @returns {Promise<string>} session_id
 */
export async function getOrCreateSession() {
  let sessionId = localStorage.getItem(SESSION_KEY);

  if (!sessionId) {
    try {
      const headers = {
        'Content-Type': 'application/json',
      };

      // Authorization 헤더 제거 - 쿠키만 사용

      const response = await fetch(`${API_BASE_URL}/chatbot/session`, {
        method: 'POST',
        headers: headers,
        credentials: 'include'  // 쿠키 자동 전송
      });

      if (!response.ok) {
        throw new Error('세션 생성 실패');
      }

      const data = await response.json();
      sessionId = data.session_id;
      localStorage.setItem(SESSION_KEY, sessionId);

      console.log('✅ 새 챗봇 세션 생성:', sessionId);
    } catch (error) {
      console.error('❌ 세션 생성 오류:', error);
      throw error;
    }
  }

  return sessionId;
}

/**
 * 챗봇에 메시지 전송
 * @param {string} userMessage - 사용자 입력 메시지
 * @returns {Promise<string>} 챗봇 응답 메시지
 */
export async function sendChatMessage(userMessage) {
  try {
    // HR 관련 질문이면 RAG API로 라우팅
    if (isHRQuestion(userMessage)) {
      console.log('🔍 HR 질문 감지 - RAG 모듈로 라우팅');
      const ragResponse = await queryHRDocument(userMessage);

      if (ragResponse.type === 'error') {
        throw new Error(ragResponse.data);
      }

      return ragResponse.data; // RAG 답변 반환
    }

    // 일반 질문은 기존 챗봇 API 사용
    let sessionId = await getOrCreateSession();

    console.log('📨 챗봇 메시지 전송:', userMessage);
    console.log('🔍 세션 ID:', sessionId);

    const headers = {
      'Content-Type': 'application/json',
    };

    // Authorization 헤더 제거 - 쿠키만 사용

    const response = await fetch(`${API_BASE_URL}/chatbot/message`, {
      method: 'POST',
      headers: headers,
      credentials: 'include',  // 쿠키 자동 전송
      body: JSON.stringify({
        session_id: sessionId,
        message: userMessage
      })
    });

    // 404 에러 = 세션이 백엔드에 없음 (재시작 등으로 메모리에서 삭제됨)
    if (response.status === 404) {
      console.warn('⚠️  세션이 만료되었습니다. 새 세션을 생성합니다.');

      // localStorage의 오래된 세션 삭제
      localStorage.removeItem(SESSION_KEY);

      // 새 세션 생성
      sessionId = await getOrCreateSession();

      // 재시도
      const retryHeaders = {
        'Content-Type': 'application/json',
      };

      // Authorization 헤더 제거 - 쿠키만 사용

      const retryResponse = await fetch(`${API_BASE_URL}/chatbot/message`, {
        method: 'POST',
        headers: retryHeaders,
        credentials: 'include',  // 쿠키 자동 전송
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage
        })
      });

      if (!retryResponse.ok) {
        throw new Error(`Chatbot API 재시도 실패: ${retryResponse.status}`);
      }

      const retryResult = await retryResponse.json();
      console.log('🤖 챗봇 응답 (재시도):', retryResult);
      return retryResult.assistant_message;
    }

    if (!response.ok) {
      throw new Error(`Chatbot API 호출 실패: ${response.status}`);
    }

    const result = await response.json();
    console.log('🤖 챗봇 응답:', result);

    return result.assistant_message;
  } catch (error) {
    console.error('❌ Chatbot API 오류:', error);
    throw error;
  }
}

/**
 * 대화 히스토리 조회
 * @returns {Promise<Array>} 대화 히스토리
 */
export async function getChatHistory() {
  try {
    const sessionId = await getOrCreateSession();

    const response = await fetch(`${API_BASE_URL}/chatbot/history/${sessionId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include'  // 쿠키 자동 전송
    });

    if (!response.ok) {
      throw new Error('히스토리 조회 실패');
    }

    const result = await response.json();
    return result.messages || [];
  } catch (error) {
    console.error('❌ 히스토리 조회 오류:', error);
    return [];
  }
}

/**
 * 세션 삭제
 */
export async function deleteChatSession() {
  try {
    const sessionId = localStorage.getItem(SESSION_KEY);
    if (!sessionId) return;

    await fetch(`${API_BASE_URL}/chatbot/session/${sessionId}`, {
      method: 'DELETE',
      credentials: 'include'  // 쿠키 자동 전송
    });

    localStorage.removeItem(SESSION_KEY);
    console.log('✅ 챗봇 세션 삭제 완료');
  } catch (error) {
    console.error('❌ 세션 삭제 오류:', error);
  }
}

// ============================================
// Multi-Agent 시스템 API
// ============================================

/**
 * Multi-Agent 세션 ID 가져오기 (없으면 새로 생성)
 * @returns {Promise<string>} session_id
 */
export async function getOrCreateMultiAgentSession() {
  let sessionId = localStorage.getItem(MULTI_AGENT_SESSION_KEY);

  if (!sessionId) {
    try {
      const headers = {
        'Content-Type': 'application/json',
      };

      // Authorization 헤더 제거 - 쿠키만 사용

      const response = await fetch(`${API_BASE_URL}/multi-agent/session`, {
        method: 'POST',
        headers: headers,
        credentials: 'include',  // 쿠키 자동 전송
        body: JSON.stringify({})
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`❌ Multi-Agent 세션 생성 실패: ${response.status} ${response.statusText}`, errorText);
        throw new Error(`Multi-Agent 세션 생성 실패: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      sessionId = data.session_id;
      localStorage.setItem(MULTI_AGENT_SESSION_KEY, sessionId);

      console.log('✅ Multi-Agent 세션 생성:', sessionId);
    } catch (error) {
      console.error('❌ Multi-Agent 세션 생성 오류:', error);
      // 세션 생성 실패해도 기존 세션이 있으면 사용, 없으면 임시 세션 ID 생성
      if (!sessionId) {
        console.warn('⚠️ 세션 생성 실패, 임시 세션 ID 사용');
        sessionId = `temp_${Date.now()}`;
        localStorage.setItem(MULTI_AGENT_SESSION_KEY, sessionId);
      }
      // 에러를 throw하지 않고 임시 세션으로 진행
    }
  }

  return sessionId;
}

/**
 * Multi-Agent 시스템에 메시지 전송
 * @param {string} userMessage - 사용자 입력 메시지
 * @returns {Promise<Object>} Multi-Agent 응답 객체
 */
export async function sendMultiAgentMessage(userMessage) {
  try {
    console.log('🤖 Multi-Agent 메시지 전송:', userMessage);

    // 세션 ID 가져오기 (실패해도 계속 진행)
    let sessionId = null;
    try {
      sessionId = await getOrCreateMultiAgentSession();
    } catch (error) {
      console.warn('⚠️ 세션 생성 실패, 세션 없이 진행:', error);
      // 세션 없이도 진행 가능 (백엔드가 선택적으로 처리)
    }

    const headers = {
      'Content-Type': 'application/json',
    };

    // Authorization 헤더 제거 - 쿠키만 사용
    // 백엔드가 쿠키에서 access_token을 자동으로 읽음

    // 쿠키에서 user ID 가져오기
    let userId = null;
    try {
      const userCookie = document.cookie.split('; ').find(row => row.startsWith('user='));
      if (userCookie) {
        const userJson = decodeURIComponent(userCookie.split('=')[1]);
        const userData = JSON.parse(userJson);
        userId = userData.id;
      }
    } catch (error) {
      console.warn('⚠️ user 쿠키 파싱 실패:', error);
    }

    const requestBody = {
      query: userMessage
    };

    if (sessionId) {
      requestBody.session_id = sessionId;
    }

    if (userId) {
      requestBody.user_id = userId;
    }

    const response = await fetch(`${API_BASE_URL}/multi-agent/query`, {
      method: 'POST',
      headers: headers,
      credentials: 'include',  // 쿠키 자동 전송
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`❌ Multi-Agent API 호출 실패: ${response.status} ${response.statusText}`, errorText);
      throw new Error(`Multi-Agent API 호출 실패: ${response.status} ${response.statusText}`);
    }

    const result = await response.json();
    console.log('🤖 Multi-Agent 응답:', result);

    return result;

  } catch (error) {
    console.error('❌ Multi-Agent API 오류:', error);
    throw error;
  }
}

/**
 * 사용 가능한 에이전트 목록 조회
 * @returns {Promise<Array>} 에이전트 목록
 */
export async function getAvailableAgents() {
  try {
    const headers = {
      'Content-Type': 'application/json',
    };

    // Authorization 헤더 제거 - 쿠키만 사용

    const response = await fetch(`${API_BASE_URL}/multi-agent/agents`, {
      method: 'GET',
      headers: headers,
      credentials: 'include'  // 쿠키 자동 전송
    });

    if (!response.ok) {
      throw new Error('에이전트 목록 조회 실패');
    }

    const agents = await response.json();
    console.log('📋 사용 가능한 에이전트:', agents);

    return agents;

  } catch (error) {
    console.error('❌ 에이전트 목록 조회 오류:', error);
    return [];
  }
}

/**
 * Multi-Agent 시스템 헬스 체크
 * @returns {Promise<Object>} 헬스 체크 결과
 */
export async function checkMultiAgentHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/multi-agent/health`, {
      method: 'GET',
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error('헬스 체크 실패');
    }

    const health = await response.json();
    console.log('💚 Multi-Agent 헬스 체크:', health);

    return health;

  } catch (error) {
    console.error('❌ 헬스 체크 오류:', error);
    return { status: 'unhealthy', error: error.message };
  }
}

