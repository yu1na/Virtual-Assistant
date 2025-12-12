/**
 * 채팅 서비스 모듈
 * 백엔드 API 호출을 담당
 * 
 * Multi-Agent 시스템 사용: Supervisor가 자동으로 적절한 에이전트로 라우팅
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';
const MULTI_AGENT_SESSION_KEY = 'multi_agent_session_id';

// 토큰 저장
let accessToken = null;

/**
 * 액세스 토큰 설정
 * @param {string} token - JWT 액세스 토큰
 */
export function setAccessToken(token) {
  accessToken = token;
  console.log('✅ 액세스 토큰 설정됨');
}

/**
 * Multi-Agent 세션 ID 가져오기 (없으면 새로 생성)
 * @returns {Promise<string>} session_id
 */
async function getOrCreateMultiAgentSession() {
  let sessionId = localStorage.getItem(MULTI_AGENT_SESSION_KEY);

  if (!sessionId) {
    try {
      const headers = {
        'Content-Type': 'application/json',
      };

      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }

      const response = await fetch(`${API_BASE_URL}/multi-agent/session`, {
        method: 'POST',
        headers: headers,
        credentials: 'include',
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error('Multi-Agent 세션 생성 실패');
      }

      const data = await response.json();
      sessionId = data.session_id;
      localStorage.setItem(MULTI_AGENT_SESSION_KEY, sessionId);

      console.log('✅ Multi-Agent 세션 생성:', sessionId);
    } catch (error) {
      console.error('❌ Multi-Agent 세션 생성 오류:', error);
      throw error;
    }
  }

  return sessionId;
}

/**
 * 챗봇에게 메시지를 전송하고 응답을 받음
 * Multi-Agent Supervisor가 자동으로 적절한 에이전트로 라우팅
 * @param {string} userText - 사용자 입력 텍스트
 * @returns {Promise<{type: string, data: any}>} 챗봇 응답 (type과 data 포함)
 */
export async function callChatModule(userText, history = []) {
  console.log('📨 사용자 메시지:', userText);

  try {
    // Multi-Agent 세션 ID 가져오기
    const sessionId = await getOrCreateMultiAgentSession();

    const headers = {
      'Content-Type': 'application/json',
    };

    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    // Multi-Agent API 호출 (Supervisor가 자동 라우팅)
    const response = await fetch(`${API_BASE_URL}/multi-agent/query`, {
      method: 'POST',
      headers: headers,
      credentials: 'include',
      body: JSON.stringify({
        query: userText,
        session_id: sessionId,
        context: {
          conversation_history: history.map(msg => ({
            role: msg.role,
            content: msg.text,
            agent_used: msg.agent // 에이전트 정보도 포함
          }))
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Multi-Agent API 호출 실패: ${response.status}`);
    }

    const result = await response.json();
    console.log('🤖 Multi-Agent 응답:', result);

    // 사용된 에이전트에 따라 응답 타입 결정
    const agentUsed = result.agent_used || 'unknown';

    // therapy_tool이 사용된 경우
    if (agentUsed === 'therapy_tool') {
      return {
        type: 'therapy',
        data: result.answer,
        mode: 'adler', // 기본값
        agent_used: agentUsed
      };
    }

    // planner_tool이 사용되고 task_recommendations 형식인 경우
    // (planner_tool의 응답 형식에 따라 조정 필요)
    if (agentUsed === 'planner_tool' && result.answer.includes('추천')) {
      // planner_tool이 task_recommendations 형식으로 응답하는지 확인 필요
      // 일단 일반 텍스트로 처리
    }

    // 일반 텍스트 응답
    return {
      type: 'text',
      data: result.answer,
      agent_used: agentUsed
    };

  } catch (error) {
    console.error('❌ Multi-Agent API 오류:', error);
    return {
      type: 'error',
      data: '응답을 가져오는 중 오류가 발생했습니다. 백엔드 서버를 확인해주세요.'
    };
  }
}

// ============================================
// [주석 처리] 기존 수동 라우팅 코드
// Multi-Agent Supervisor가 자동으로 라우팅하므로 더 이상 필요 없음
// ============================================

/*
// 세션 ID 저장 (기존 챗봇용)
let sessionId = null;

// 세션 초기화 (기존 챗봇용)
async function initSession() {
  if (sessionId) return sessionId;
  
  try {
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
    
    const response = await fetch(`${API_BASE_URL}/chatbot/session`, {
      method: 'POST',
      headers: headers
    });
    
    if (!response.ok) {
      throw new Error(`세션 생성 실패: ${response.status}`);
    }
    
    const result = await response.json();
    sessionId = result.session_id;
    console.log('✅ 챗봇 세션 생성:', sessionId);
    return sessionId;
  } catch (error) {
    console.error('❌ 세션 생성 오류:', error);
    throw error;
  }
}

// 심리 상담 관련 키워드 확인 (수동 라우팅)
function isTherapyRelated(text) {
  const therapyKeywords = [
    '힘들어', '상담', '짜증', '우울', '불안', '스트레스',
    '고민', '걱정', '슬프', '외로', '화나', '답답',
    '아들러', 'adler', 'counseling', 'therapy', 'help',
    'depressed', 'anxious', '심리'
  ];
  
  const lowerText = text.toLowerCase();
  return therapyKeywords.some(keyword => lowerText.includes(keyword));
}

// 심리 상담 메시지 전송 (수동 라우팅)
async function sendTherapyMessage(userText) {
  try {
    const response = await fetch(`${API_BASE_URL}/therapy/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: userText
      })
    });
    
    if (!response.ok) {
      throw new Error(`심리 상담 API 호출 실패: ${response.status}`);
    }
    
    const result = await response.json();
    console.log('🎭 아들러 상담사 응답:', result);
    
    return {
      type: 'therapy',
      data: result.answer,
      mode: result.mode,
      used_chunks: result.used_chunks
    };
  } catch (error) {
    console.error('❌ 심리 상담 API 오류:', error);
    return {
      type: 'error',
      data: '심리 상담 시스템에 연결할 수 없습니다. 백엔드 서버를 확인해주세요.'
    };
  }
}

// 챗봇 메시지 전송 (기존 챗봇 API)
async function sendChatbotMessage(userText) {
  try {
    await initSession();
    
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
    
    const response = await fetch(`${API_BASE_URL}/chatbot/message`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        session_id: sessionId,
        message: userText
      })
    });
    
    if (!response.ok) {
      throw new Error(`챗봇 API 호출 실패: ${response.status}`);
    }
    
    const result = await response.json();
    console.log('🤖 챗봇 응답:', result);
    
    return {
      type: 'text',
      data: result.assistant_message
    };
  } catch (error) {
    console.error('❌ 챗봇 API 오류:', error);
    return {
      type: 'error',
      data: '챗봇 응답을 가져오는 중 오류가 발생했습니다. 로그인이 필요할 수 있습니다.'
    };
  }
}

// 오늘 추천 업무 가져오기 (수동 라우팅)
// taskService.js의 getTodayPlan() 함수 사용
// import { getTodayPlan } from '../report/taskService.js';
// 
// "오늘 뭐할지 추천" 등의 키워드가 있으면 TodayPlan API 호출
// if (userText.includes('오늘') && (userText.includes('추천') || userText.includes('뭐할'))) {
//   return await getTodayPlan();
// }
*/

/**
 * 선택한 업무 저장 (taskService.js에서 re-export)
 * chatPanel.js에서 사용하기 위해 유지
 */
export { saveSelectedTasks } from '../report/taskService.js';
