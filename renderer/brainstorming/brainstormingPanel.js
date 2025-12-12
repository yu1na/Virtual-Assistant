/**
 * 브레인스토밍 패널 UI 및 상태 관리
 * Cmd/Ctrl + Shift + B로 토글 가능
 */

import { brainstormingService } from './brainstormingService.js';

// 패널 표시 상태
let isPanelVisible = true;

// 현재 세션 ID
let currentSessionId = null;

// 현재 단계
let currentStep = 'initial'; // initial, q1, q2, q3, ideas, complete

// DOM 요소 참조
let bsPanel = null;
let bsContent = null;
let bsInput = null;
let bsSubmitBtn = null;

/**
 * 브레인스토밍 패널 초기화
 */
export function initBrainstormingPanel() {
  console.log('💡 브레인스토밍 패널 초기화 중...');
  
  // DOM 요소 가져오기
  bsPanel = document.getElementById('brainstorming-panel');
  bsContent = document.getElementById('bs-content');
  bsInput = document.getElementById('bs-input');
  bsSubmitBtn = document.getElementById('bs-submit-btn');
  
  if (!bsPanel || !bsContent || !bsInput || !bsSubmitBtn) {
    console.error('❌ 브레인스토밍 패널 요소를 찾을 수 없습니다.');
    return;
  }
  
  // 초기 메시지 표시
  showInitialMessage();
  
  // 이벤트 리스너 등록
  setupEventListeners();
  
  console.log('✅ 브레인스토밍 패널 초기화 완료');
}

/**
 * 이벤트 리스너 설정
 */
function setupEventListeners() {
  // 제출 버튼 클릭
  bsSubmitBtn.addEventListener('click', handleSubmit);
  
  // Enter 키로 전송
  bsInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  });
  
  // Cmd/Ctrl + Shift + B로 패널 토글
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'b') {
      e.preventDefault();
      togglePanel();
    }
  });
}

/**
 * 초기 메시지 표시
 */
function showInitialMessage() {
  addMessage('system', '안녕하세요! 브레인스토밍을 시작하시겠습니까?');
  addMessage('system', '시작하려면 "시작" 또는 "start"를 입력하세요.');
  currentStep = 'initial';
}

/**
 * 제출 핸들러
 */
async function handleSubmit() {
  const text = bsInput.value.trim();
  
  if (!text) return;
  
  // 사용자 메시지 추가
  addMessage('user', text);
  
  // 입력창 초기화
  bsInput.value = '';
  
  // 버튼 비활성화 (응답 대기)
  bsSubmitBtn.disabled = true;
  bsSubmitBtn.textContent = '...';
  
  try {
    // 현재 단계에 따라 처리
    switch (currentStep) {
      case 'initial':
        await handleInitial(text);
        break;
      case 'q1':
        await handleQ1(text);
        break;
      case 'q2':
        await handleQ2(text);
        break;
      case 'q3':
        await handleQ3(text);
        break;
      case 'delete_confirm':
        await handleDeleteConfirm(text);
        break;
      default:
        addMessage('system', '알 수 없는 단계입니다. "시작"을 입력하여 다시 시작하세요.');
    }
  } catch (error) {
    console.error('처리 중 오류:', error);
    addMessage('system', `오류가 발생했습니다: ${error.message}`);
  } finally {
    // 버튼 활성화
    bsSubmitBtn.disabled = false;
    bsSubmitBtn.textContent = '전송';
  }
}

/**
 * 초기 단계 처리
 */
async function handleInitial(text) {
  const lowerText = text.toLowerCase();
  
  if (lowerText === '시작' || lowerText === 'start') {
    // 세션 생성
    const response = await brainstormingService.createSession();
    currentSessionId = response.session_id;
    
    addMessage('system', response.message);
    addMessage('system', 'Q1: 어디에 쓸 아이디어가 필요하신가요?');
    addMessage('system', '(예: 모바일 앱, 마케팅 캠페인, 신제품 기획 등)');
    
    currentStep = 'q1';
  } else {
    addMessage('system', '"시작" 또는 "start"를 입력하여 브레인스토밍을 시작하세요.');
  }
}

/**
 * Q1 처리 (목적 입력)
 */
async function handleQ1(text) {
  if (!currentSessionId) {
    addMessage('system', '세션이 없습니다. "시작"을 입력하여 다시 시작하세요.');
    currentStep = 'initial';
    return;
  }
  
  // 목적 제출
  const response = await brainstormingService.submitPurpose(currentSessionId, text);
  addMessage('system', `✅ ${response.message}`);
  
  // 워밍업 질문 요청
  addMessage('system', '🤔 워밍업 질문을 생성하고 있습니다...');
  
  const warmupResponse = await brainstormingService.getWarmup(currentSessionId);
  
  addMessage('system', 'Q2: 브레인스토밍 워밍업');
  warmupResponse.questions.forEach((q, i) => {
    addMessage('system', `${i + 1}. ${q}`);
  });
  
  addMessage('system', '준비되셨으면 "네" 또는 "yes"를 입력하세요.');
  
  currentStep = 'q2';
}

/**
 * Q2 처리 (워밍업 확인)
 */
async function handleQ2(text) {
  const lowerText = text.toLowerCase();
  
  if (lowerText === '네' || lowerText === 'yes') {
    // 워밍업 확인
    const response = await brainstormingService.confirmWarmup(currentSessionId);
    addMessage('system', response.message);
    
    addMessage('system', 'Q3: 지금부터 떠오르는 무엇이든 자유롭게 많이 적어주세요.');
    addMessage('system', '(쉼표로 구분하여 입력하세요. 예: 아이디어1, 아이디어2, 아이디어3)');
    addMessage('system', '최소 10개 이상 입력해주세요.');
    
    currentStep = 'q3';
  } else {
    addMessage('system', '"네" 또는 "yes"를 입력하여 다음 단계로 진행하세요.');
  }
}

/**
 * Q3 처리 (자유연상 입력)
 */
async function handleQ3(text) {
  // 쉼표로 분리
  const associations = text.split(',').map(s => s.trim()).filter(s => s);
  
  if (associations.length < 10) {
    addMessage('system', `⚠️ 최소 10개 이상 입력해주세요. (현재: ${associations.length}개)`);
    addMessage('system', '더 많은 키워드를 추가하여 다시 입력하세요.');
    return;
  }
  
  // 자유연상 제출
  const response = await brainstormingService.submitAssociations(currentSessionId, associations);
  addMessage('system', `✅ ${response.message} (${response.count}개)`);
  
  // 아이디어 생성 요청
  addMessage('system', '💡 아이디어를 생성하고 있습니다... (약 30초 소요)');
  
  const ideasResponse = await brainstormingService.generateIdeas(currentSessionId);
  
  // 아이디어 표시
  addMessage('system', '\n🎉 아이디어가 생성되었습니다!\n');
  
  ideasResponse.ideas.forEach((idea, i) => {
    addMessage('idea', `\n📌 아이디어 ${i + 1}: ${idea.title}\n\n${idea.description}\n\n📊 SWOT 분석:\n${idea.analysis}`);
  });
  
  addMessage('system', '\n모든 데이터를 삭제하시겠습니까? (네/아니오)');
  
  currentStep = 'delete_confirm';
}

/**
 * 삭제 확인 처리
 */
async function handleDeleteConfirm(text) {
  const lowerText = text.toLowerCase();
  
  if (lowerText === '네' || lowerText === 'yes') {
    // 세션 삭제
    const response = await brainstormingService.deleteSession(currentSessionId);
    addMessage('system', `✅ ${response.message}`);
    
    // 초기화
    currentSessionId = null;
    currentStep = 'initial';
    
    addMessage('system', '\n다시 시작하려면 "시작"을 입력하세요.');
  } else {
    addMessage('system', '세션이 유지됩니다. 종료하려면 창을 닫으세요.');
    
    // 초기화 (세션은 유지)
    currentStep = 'initial';
  }
}

/**
 * 메시지 추가
 */
function addMessage(type, text) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `bs-message ${type}`;
  
  const bubble = document.createElement('div');
  bubble.className = 'bs-bubble';
  bubble.textContent = text;
  
  messageDiv.appendChild(bubble);
  bsContent.appendChild(messageDiv);
  
  // 스크롤을 최하단으로
  bsContent.scrollTop = bsContent.scrollHeight;
}

/**
 * 패널 토글 (Cmd/Ctrl + Shift + B)
 */
export function togglePanel() {
  isPanelVisible = !isPanelVisible;
  
  if (isPanelVisible) {
    bsPanel.style.display = 'flex';
    bsPanel.style.opacity = '1';
    bsPanel.style.transform = 'translateY(0)';
  } else {
    bsPanel.style.opacity = '0';
    bsPanel.style.transform = 'translateY(-20px)';
    setTimeout(() => {
      bsPanel.style.display = 'none';
    }, 300);
  }
}

