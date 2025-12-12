/**
 * 브레인스토밍 서비스
 * brainstorming.py API 연동
 */

const API_BASE = 'http://localhost:8000/api/v1/brainstorming';

// 🔥 전역으로 export (init()에서 호출)
window.initBrainstormingPanel = null;

// 세션 ID를 외부에서 접근 가능하도록 export
export function getCurrentSessionId() {
  return currentSessionId;
}

// 세션 삭제 함수 export
export async function deleteCurrentSession() {
  if (!currentSessionId) {
    console.log('⚠️  삭제할 세션이 없습니다.');
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE}/session/${currentSessionId}`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      console.log('✅ 세션 삭제 완료:', currentSessionId);
      currentSessionId = null;
    } else {
      console.error('❌ 세션 삭제 실패:', response.status);
    }
  } catch (error) {
    console.error('❌ 세션 삭제 오류:', error);
  }
}

// 패널 표시 상태
let isBsPanelVisible = false;

// 현재 세션 ID
let currentSessionId = null;

// 현재 단계
let currentStep = 'initial'; // initial, q1, q2, q3, ideas, delete_confirm (save_confirm 제거 - 버튼으로 대체)

// Q3 누적 키워드 저장
let accumulatedKeywords = [];

// Q3 동적 메시지 요소 (고정 위치에 갱신)
let dynamicMessageElement = null;

// Q3 생성 버튼 요소
let generateButtonElement = null;

// 생성된 아이디어 저장 (DB 저장용)
let generatedIdeas = [];

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
  
  // 🍪 쿠키 디버깅
  console.log('🍪 [Brainstorming] 쿠키 확인 시작');
  console.log('   전체 쿠키:', document.cookie);
  console.log('   쿠키 길이:', document.cookie.length);
  
  const accessToken = getCookie('access_token');
  const refreshToken = getCookie('refresh_token');
  const user = getCookie('user');
  const loggedIn = getCookie('logged_in');
  
  console.log('   access_token:', accessToken ? `${accessToken.substring(0, 20)}... (길이: ${accessToken.length})` : 'null');
  console.log('   refresh_token:', refreshToken ? `${refreshToken.substring(0, 20)}...` : 'null');
  console.log('   user:', user ? `${user.substring(0, 30)}...` : 'null');
  console.log('   logged_in:', loggedIn);
  console.log('🍪 [Brainstorming] 쿠키 확인 완료');
  
  bsPanel = document.getElementById('brainstorming-panel');
  bsContent = document.getElementById('bs-content');
  bsInput = document.getElementById('bs-input');
  bsSubmitBtn = document.getElementById('bs-submit-btn');
  
  if (!bsPanel || !bsContent || !bsInput || !bsSubmitBtn) {
    console.error('❌ 브레인스토밍 패널 요소를 찾을 수 없습니다.');
    return;
  }
  
  // 🔥 기존 내용 초기화
  bsContent.innerHTML = '';
  
  // 초기 메시지 표시
  showInitialBsMessage();
  
  // 이벤트 리스너 등록
  setupBsEventListeners();
  
  console.log('✅ 브레인스토밍 패널 초기화 완료');
}

// 🔥 전역으로 export
window.initBrainstormingPanel = initBrainstormingPanel;

/**
 * 이벤트 리스너 설정
 */
function setupBsEventListeners() {
  // 제출 버튼 클릭
  bsSubmitBtn.addEventListener('click', handleBsSubmit);
  
  // Enter 키로 전송 (한글 입력 중 방지)
  bsInput.addEventListener('keydown', (e) => {
    // 🔥 한글 입력 중(composing)이면 무시
    if (e.isComposing || e.keyCode === 229) {
      return;
    }
    
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleBsSubmit();
    }
  });
  
  // 💾 저장된 아이디어 버튼
  const toggleBtn = document.getElementById('toggle-saved-ideas-btn');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleSavedIdeas);
    
    // 호버 효과
    toggleBtn.addEventListener('mouseenter', () => {
      toggleBtn.style.transform = 'scale(1.05)';
      toggleBtn.style.background = '#5A7A6A';
    });
    
    toggleBtn.addEventListener('mouseleave', () => {
      toggleBtn.style.transform = 'scale(1)';
      toggleBtn.style.background = '#6B9080';
    });
  }
}

/**
 * 초기 메시지 표시
 */
function showInitialBsMessage() {
  addBsMessage('system', '안녕하세요! 어디에 쓸 아이디어가 필요하신가요? 🤔');
  addBsMessage('system', '(예: 모바일 앱, 마케팅 캠페인, 신제품 기획 등)');
  
  // 🔥 세션 자동 생성
  createSession();
  
  currentStep = 'q1'; // 바로 Q1으로 시작
}

/**
 * 세션 자동 생성
 */
async function createSession() {
  try {
    const response = await fetch(`${API_BASE}/session`, { method: 'POST' });
    const data = await response.json();
    
    currentSessionId = data.session_id;
    console.log('✅ 세션 생성:', currentSessionId);
  } catch (error) {
    console.error('❌ 세션 생성 실패:', error);
    addBsMessage('system', '세션 생성에 실패했습니다. 새로고침 후 다시 시도하세요.');
  }
}

/**
 * 제출 처리
 */
async function handleBsSubmit() {
  const text = bsInput.value.trim();
  
  if (!text) return;
  
  // 🔥 전송 중이면 무시 (중복 전송 방지)
  if (bsSubmitBtn.disabled) {
    console.log('⚠️  이미 전송 중...');
    return;
  }
  
  // 🔥 Q3 단계에서는 채팅창에 표시하지 않음 (키워드 태그로만 표시)
  if (currentStep !== 'q3') {
    addBsMessage('user', text);
  }
  
  // 🔥 입력창 초기화 (IME 문제 해결)
  bsInput.value = '';
  bsInput.blur(); // 포커스 제거
  setTimeout(() => {
    bsInput.focus(); // 다시 포커스
  }, 0);
  
  bsSubmitBtn.disabled = true;
  bsSubmitBtn.textContent = '...';
  
  try {
    switch (currentStep) {
      case 'q1':
        await handleBsQ1(text);
        break;
      case 'q2':
        await handleBsQ2(text);
        break;
      case 'q3':
        await handleBsQ3(text);
        break;
      case 'delete_confirm':
        await handleBsDeleteConfirm(text);
        break;
      default:
        addBsMessage('system', '알 수 없는 단계입니다. 창을 닫고 다시 시작하세요.');
    }
  } catch (error) {
    console.error('처리 중 오류:', error);
    addBsMessage('system', `오류가 발생했습니다: ${error.message}`);
  } finally {
    bsSubmitBtn.disabled = false;
    bsSubmitBtn.textContent = '전송';
  }
}

/**
 * Q1 처리
 */
async function handleBsQ1(text) {
  if (!currentSessionId) {
    addBsMessage('system', '세션이 없습니다. 창을 닫고 다시 시작하세요.');
    return;
  }
  
  const response = await fetch(`${API_BASE}/purpose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSessionId, purpose: text })
  });
  const data = await response.json();
  
  addBsMessage('system', `✅ ${data.message}`);
  addBsMessage('system', '🤔 워밍업 질문을 생성하고 있습니다...');
  
  const warmupResponse = await fetch(`${API_BASE}/warmup/${currentSessionId}`);
  const warmupData = await warmupResponse.json();
  
  // 🔥 화면 클리어 후 Q2 표시
  setTimeout(() => {
    bsContent.innerHTML = '';
    
    // 질문들을 굵고 중앙 정렬로 표시
    warmupData.questions.forEach((q) => {
      addBsMessage('warmup', q);
    });
    
    // 🔥 안내 메시지 + 시작 버튼을 하나의 예쁜 박스로 표시
    const instructionBox = document.createElement('div');
    instructionBox.style.cssText = `
      background: rgba(156, 175, 136, 0.08);
      border: 2px solid rgba(156, 175, 136, 0.3);
      border-radius: 16px;
      padding: 24px;
      margin: 30px auto;
      max-width: 85%;
      text-align: center;
      line-height: 1.8;
      color: #2c3e50;
      font-size: 15px;
    `;
    
    instructionBox.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 15px; font-size: 16px;">
        잠시 후 자유롭게 문장, 단어들을 입력하세요.
      </div>
      <div style="font-size: 14px; color: #666; margin: 10px 0;">
        예시) 단어, 단어, 문장 ⏎<br>
        예시) 단어 ⏎
      </div>
    `;
    
    // 🚀 시작하기 버튼 생성
    const startButton = document.createElement('button');
    startButton.textContent = '🚀 시작하기';
    startButton.style.cssText = `
      background: linear-gradient(135deg, #9CAF88 0%, #7A8C6F 100%);
      color: white;
      border: none;
      padding: 12px 30px;
      font-size: 16px;
      font-weight: bold;
      border-radius: 8px;
      cursor: pointer;
      margin-top: 20px;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(156, 175, 136, 0.3);
    `;
    
    // 호버 효과
    startButton.addEventListener('mouseenter', () => {
      startButton.style.transform = 'translateY(-2px)';
      startButton.style.boxShadow = '0 6px 20px rgba(156, 175, 136, 0.4)';
    });
    
    startButton.addEventListener('mouseleave', () => {
      startButton.style.transform = 'translateY(0)';
      startButton.style.boxShadow = '0 4px 15px rgba(156, 175, 136, 0.3)';
    });
    
    // 클릭 시 Q3로 진행
    startButton.addEventListener('click', async () => {
      startButton.disabled = true;
      startButton.textContent = '⏳ 시작 중...';
      
      // Q3로 진행
      const response = await fetch(`${API_BASE}/confirm/${currentSessionId}`, { method: 'POST' });
      const data = await response.json();
      
      // 🔥 화면 클리어 후 Q3 표시
      setTimeout(() => {
        bsContent.innerHTML = '';
        
        // 🔥 동적 메시지 표시 영역 생성 (고정 타이틀 + 동적 메시지)
        createDynamicMessageArea();
        
        // 초기 메시지 표시
        updateDynamicMessage();
      }, 500);
      
      // Q3 누적 키워드 초기화
      accumulatedKeywords = [];
      currentStep = 'q3';
    });
    
    instructionBox.appendChild(startButton);
    bsContent.appendChild(instructionBox);
  }, 1000); // 1초 후 클리어
  
  currentStep = 'q2';
}

/**
 * Q2 처리 (시작 버튼으로 대체됨 - 더 이상 사용 안 함)
 */
async function handleBsQ2(text) {
  // 시작 버튼이 Q3로 직접 진행하므로 이 함수는 호출되지 않음
  console.log('⚠️ handleBsQ2는 더 이상 사용되지 않습니다.');
}

/**
 * 🔥 동적 메시지 영역 생성 (페이지 상단 고정)
 */
function createDynamicMessageArea() {
  // 기존 요소 제거
  if (dynamicMessageElement) {
    dynamicMessageElement.remove();
  }
  if (generateButtonElement) {
    generateButtonElement.remove();
  }
  
  // 🔥 고정 타이틀 생성
  const fixedTitle = document.createElement('div');
  fixedTitle.style.cssText = `
    text-align: center;
    font-size: 18px;
    font-weight: 600;
    color: #2c3e50;
    margin: 20px 0 10px 0;
    padding: 15px;
  `;
  fixedTitle.textContent = ' 지금부터 떠오르는 무엇이든 자유롭게 많이 적어주세요.';
  
  // 동적 메시지 div 생성
  dynamicMessageElement = document.createElement('div');
  dynamicMessageElement.id = 'dynamic-message';
  dynamicMessageElement.style.cssText = `
    text-align: center;
    font-size: 18px;
    font-weight: 500;
    color: #2c3e50;
    margin: 10px 0 30px 0;
    padding: 20px;
    background: rgba(156, 175, 136, 0.1);
    border-radius: 12px;
    min-height: 60px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 15px;
  `;
  
  bsContent.appendChild(fixedTitle);
  bsContent.appendChild(dynamicMessageElement);
}

/**
 * 🔥 동적 메시지 갱신 (입력 개수에 따라)
 */
function updateDynamicMessage() {
  if (!dynamicMessageElement) return;
  
  const count = accumulatedKeywords.length;
  let message = '';
  let showButton = false;
  
  if (count < 5) {
    message = '💭 떠오르는 것을 자유롭게 입력해주세요';
  } else if (count >= 5 && count <= 9) {
    message = '😊 좋아요! 조금만 더 입력해볼까요?';
  } else if (count >= 10 && count <= 14) {
    message = '🎉 많이 입력했네요~! 더 있으면 입력하고, 없으면 \'생성\'을 눌러주세요';
    showButton = true;
  } else if (count >= 15 && count < 25) {
    message = '🚀 와! 많이 입력하셨네요! 준비되셨으면 \'생성\' 버튼을 눌러주세요';
    showButton = true;
  } else {
    // 25개 도달
    message = '✅ 25개 입력 완료! 이제 아이디어를 생성해주세요 🎨';
    showButton = true;
  }
  
  // 메시지 텍스트만 업데이트 (버튼은 별도)
  const messageText = dynamicMessageElement.querySelector('.dynamic-text') || document.createElement('div');
  messageText.className = 'dynamic-text';
  messageText.textContent = message;
  
  // 기존 내용 지우고 메시지만 추가
  dynamicMessageElement.innerHTML = '';
  dynamicMessageElement.appendChild(messageText);
  
  // 버튼 표시 (10개 이상)
  if (showButton) {
    if (!generateButtonElement) {
      generateButtonElement = document.createElement('button');
      generateButtonElement.textContent = '🎨 아이디어 생성하기';
      generateButtonElement.style.cssText = `
        background: linear-gradient(135deg, #9CAF88 0%, #7A8C6F 100%);
        color: white;
        border: none;
        padding: 12px 30px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(156, 175, 136, 0.3);
      `;
      
      // 호버 효과
      generateButtonElement.addEventListener('mouseenter', () => {
        generateButtonElement.style.transform = 'translateY(-2px)';
        generateButtonElement.style.boxShadow = '0 6px 20px rgba(156, 175, 136, 0.4)';
      });
      generateButtonElement.addEventListener('mouseleave', () => {
        generateButtonElement.style.transform = 'translateY(0)';
        generateButtonElement.style.boxShadow = '0 4px 15px rgba(156, 175, 136, 0.3)';
      });
      
      // 클릭 시 아이디어 생성
      generateButtonElement.addEventListener('click', async () => {
        generateButtonElement.disabled = true;
        generateButtonElement.textContent = '생성 중...';
        await generateIdeas();
      });
    }
    
    dynamicMessageElement.appendChild(generateButtonElement);
  } else {
    // 10개 미만이면 버튼 제거
    if (generateButtonElement) {
      generateButtonElement.remove();
      generateButtonElement = null;
    }
  }
}

/**
 * Q3 처리
 */
async function handleBsQ3(text) {
  const lowerText = text.toLowerCase();
  
  // "생성" 입력 시 아이디어 생성
  if (lowerText === '생성' || lowerText === 'done') {
    if (accumulatedKeywords.length < 10) {
      addBsMessage('system', `⚠️ 최소 10개 이상 입력해주세요. (현재: ${accumulatedKeywords.length}개)`);
      return;
    }
    
    await generateIdeas();
    return;
  }
  
  // 🔥 25개 제한 체크
  if (accumulatedKeywords.length >= 25) {
    addBsMessage('system', '⚠️ 최대 25개까지만 입력 가능합니다. 이제 아이디어를 생성해주세요!');
    return;
  }
  
  // 키워드 입력 처리 (쉼표로 구분 또는 단일 입력)
  const newKeywords = text.split(',').map(s => s.trim()).filter(s => s);
  
  // 🔥 25개 초과 방지 (입력 중 초과되는 경우)
  const availableSlots = 25 - accumulatedKeywords.length;
  const keywordsToAdd = newKeywords.slice(0, availableSlots);
  const exceededKeywords = newKeywords.slice(availableSlots);
  
  if (keywordsToAdd.length > 0) {
    accumulatedKeywords.push(...keywordsToAdd);
    
    // 🔥 입력값을 동적 메시지 아래에 표시
    keywordsToAdd.forEach(keyword => {
      const keywordDiv = document.createElement('div');
      keywordDiv.style.cssText = `
        background: rgba(156, 175, 136, 0.2);
        padding: 8px 15px;
        margin: 5px;
        border-radius: 20px;
        display: inline-block;
        font-size: 14px;
        color: #2c3e50;
      `;
      keywordDiv.textContent = keyword;
      
      // dynamicMessageElement 바로 다음에 삽입
      if (dynamicMessageElement && dynamicMessageElement.nextSibling) {
        bsContent.insertBefore(keywordDiv, dynamicMessageElement.nextSibling);
      } else {
        bsContent.appendChild(keywordDiv);
      }
    });
  }
  
  // 🔥 25개 도달 시 메시지
  if (accumulatedKeywords.length >= 25) {
    addBsMessage('system', '✅ 25개 입력 완료! 이제 "생성" 버튼을 눌러주세요 🎨');
  }
  
  // 🔥 초과된 키워드 알림
  if (exceededKeywords.length > 0) {
    addBsMessage('system', `⚠️ ${exceededKeywords.length}개는 25개 제한으로 추가되지 않았습니다.`);
  }
  
  // 🔥 동적 메시지 갱신
  updateDynamicMessage();
}

/**
 * 🔥 아이디어 생성 함수 (버튼 클릭 or "생성" 입력 시)
 */
async function generateIdeas() {
  // 연관어 저장 API 호출
  const response = await fetch(`${API_BASE}/associations/${currentSessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: currentSessionId, associations: accumulatedKeywords })
  });
  const data = await response.json();
  
  addBsMessage('system', `✅ ${data.message} (${data.count}개)`);
  
  // 🔥 화면 클리어 후 로딩 스피너 표시
  setTimeout(() => {
    bsContent.innerHTML = '';
    
    // 로딩 컨테이너 생성
    const loadingContainer = document.createElement('div');
    loadingContainer.style.cssText = `
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 60px 20px;
      text-align: center;
    `;
    
    // 🔄 스피너 생성
    const spinner = document.createElement('div');
    spinner.style.cssText = `
      width: 60px;
      height: 60px;
      border: 5px solid rgba(156, 175, 136, 0.2);
      border-top-color: #9CAF88;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin-bottom: 25px;
    `;
    
    // 메시지 텍스트
    const messageText = document.createElement('div');
    messageText.style.cssText = `
      font-size: 18px;
      font-weight: 600;
      color: #2c3e50;
      margin-bottom: 10px;
    `;
    messageText.textContent = '💡 아이디어를 생성하고 있습니다...';
    
    const subText = document.createElement('div');
    subText.style.cssText = `
      font-size: 14px;
      color: #7A8C6F;
    `;
    subText.textContent = '(약 30초 소요)';
    
    loadingContainer.appendChild(spinner);
    loadingContainer.appendChild(messageText);
    loadingContainer.appendChild(subText);
    bsContent.appendChild(loadingContainer);
    
    // 🔥 CSS 애니메이션 추가 (한 번만 실행)
    if (!document.getElementById('spinner-animation')) {
      const style = document.createElement('style');
      style.id = 'spinner-animation';
      style.textContent = `
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }
  }, 1000); // 1초 후 클리어
  
  // 🔥 아이디어 생성 API 호출을 2초 후에 시작 (클리어 후)
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  try {
    const ideasResponse = await fetch(`${API_BASE}/ideas/${currentSessionId}`);
    
    console.log('🔍 API 응답 상태:', ideasResponse.status);
    
    if (!ideasResponse.ok) {
      const errorText = await ideasResponse.text();
      console.error('❌ API 오류:', errorText);
      
      try {
        const errorData = JSON.parse(errorText);
        addBsMessage('system', `❌ 오류: ${errorData.detail || '아이디어 생성 실패'}`);
      } catch {
        addBsMessage('system', `❌ 오류: ${errorText}`);
      }
      return;
    }
    
    const ideasData = await ideasResponse.json();
    console.log('🔍 받은 데이터:', ideasData);
    
    // 🔥 생성된 아이디어 저장
    generatedIdeas = ideasData.ideas || [];
    
    // 🔥 로딩 스피너 제거 후 결과 표시
    bsContent.innerHTML = '';
    
    addBsMessage('system', '\n🎉 아이디어가 생성되었습니다!\n');
    
    // 🔥 안전한 배열 체크
    if (ideasData && ideasData.ideas && Array.isArray(ideasData.ideas)) {
      if (ideasData.ideas.length === 0) {
        addBsMessage('system', '⚠️ 생성된 아이디어가 없습니다.');
      } else {
        ideasData.ideas.forEach((idea, i) => {
          // 🔥 SWOT 분석이 이미 description에 포함되어 있으면 중복 방지
          const fullContent = idea.analysis 
            ? `\n📌 아이디어 ${i + 1}: ${idea.title}\n\n${idea.description}\n\n${idea.analysis}`
            : `\n📌 아이디어 ${i + 1}: ${idea.title}\n\n${idea.description}`;
          
          addBsMessage('idea', fullContent);
        });
      }
    } else {
      console.error('⚠️ 잘못된 응답 형식:', ideasData);
      addBsMessage('system', '⚠️ 아이디어 형식 오류. 콘솔을 확인하세요.');
    }
    
    addBsMessage('system', '\n💾 이 아이디어를 저장하시겠습니까?');
    
    // 🔥 저장 버튼 2개 생성 (네/아니오)
    const buttonContainer = document.createElement('div');
    buttonContainer.style.cssText = `
      display: flex;
      gap: 15px;
      justify-content: center;
      margin: 20px 0;
    `;
    
    // ✅ 네, 저장할게요 버튼
    const saveYesBtn = document.createElement('button');
    saveYesBtn.textContent = '✅ 네, 저장할게요';
    saveYesBtn.style.cssText = `
      background: linear-gradient(135deg, #9CAF88 0%, #7A8C6F 100%);
      color: white;
      border: none;
      padding: 12px 24px;
      font-size: 15px;
      font-weight: bold;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(156, 175, 136, 0.3);
    `;
    
    saveYesBtn.addEventListener('mouseenter', () => {
      saveYesBtn.style.transform = 'translateY(-2px)';
      saveYesBtn.style.boxShadow = '0 6px 20px rgba(156, 175, 136, 0.4)';
    });
    
    saveYesBtn.addEventListener('mouseleave', () => {
      saveYesBtn.style.transform = 'translateY(0)';
      saveYesBtn.style.boxShadow = '0 4px 15px rgba(156, 175, 136, 0.3)';
    });
    
    saveYesBtn.addEventListener('click', async () => {
      saveYesBtn.disabled = true;
      saveNoBtn.disabled = true;
      saveYesBtn.textContent = '💾 저장 중...';
      
      // 저장 로직 실행
      await handleSaveIdeas();
    });
    
    // ❌ 아니요 버튼
    const saveNoBtn = document.createElement('button');
    saveNoBtn.textContent = '❌ 아니요, 저장 안 할게요';
    saveNoBtn.style.cssText = `
      background: linear-gradient(135deg, #e0e0e0 0%, #c0c0c0 100%);
      color: #555;
      border: none;
      padding: 12px 24px;
      font-size: 15px;
      font-weight: bold;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    `;
    
    saveNoBtn.addEventListener('mouseenter', () => {
      saveNoBtn.style.transform = 'translateY(-2px)';
      saveNoBtn.style.boxShadow = '0 6px 20px rgba(0, 0, 0, 0.15)';
    });
    
    saveNoBtn.addEventListener('mouseleave', () => {
      saveNoBtn.style.transform = 'translateY(0)';
      saveNoBtn.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.1)';
    });
    
    saveNoBtn.addEventListener('click', async () => {
      saveYesBtn.disabled = true;
      saveNoBtn.disabled = true;
      saveNoBtn.textContent = '⏳ 종료 중...';
      
      // 저장하지 않고 종료
      addBsMessage('system', '저장하지 않고 종료합니다.');
      await deleteSessionAndClose();
    });
    
    buttonContainer.appendChild(saveYesBtn);
    buttonContainer.appendChild(saveNoBtn);
    bsContent.appendChild(buttonContainer);
    
    // currentStep은 'save_confirm'으로 설정하지 않음 (버튼으로 처리)
    
  } catch (error) {
    console.error('❌ 아이디어 생성 중 오류:', error);
    addBsMessage('system', `❌ 오류 발생: ${error.message}`);
    return;
  }
}

/**
 * 💾 아이디어 저장 로직
 */
async function handleSaveIdeas() {
  addBsMessage('system', '💾 아이디어를 저장하는 중...');
  
  try {
    // 저장할 데이터 준비
    if (!generatedIdeas || generatedIdeas.length === 0) {
      addBsMessage('system', '❌ 저장할 아이디어가 없습니다.');
      await deleteSessionAndClose();
      return;
    }
    
    // 모든 아이디어를 하나의 문서로 합치기
    const ideaData = {
      title: `브레인스토밍 결과 - ${new Date().toLocaleDateString()}`,
      description: JSON.stringify({
        ideas: generatedIdeas,
        created_at: new Date().toISOString()
      })
    };
    
    // Authorization 헤더 없이 요청
    // 백엔드가 쿠키에서 access_token을 자동으로 읽음
    const response = await fetch('http://localhost:8000/api/v1/brainstorming/ideas', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',  // 쿠키 자동 전송
      body: JSON.stringify(ideaData)
    });
    
    if (response.status === 401) {
      addBsMessage('system', '❌ 로그인이 필요합니다.');
      await deleteSessionAndClose();
      return;
    }
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || '저장 실패');
    }
    
    const savedData = await response.json();
    addBsMessage('system', `✅ 아이디어가 저장되었습니다! (ID: ${savedData.id})`);
    
    // 🔄 저장된 아이디어 캐시 갱신
    refreshSavedIdeasCache();
    
  } catch (error) {
    console.error('❌ 저장 실패:', error);
    addBsMessage('system', `❌ 저장 실패: ${error.message}`);
  }
  
  // 저장 완료 후 세션 삭제 + 창 닫기
  await deleteSessionAndClose();
}

/**
 * 저장 확인 처리 (버튼으로 대체됨 - 더 이상 사용 안 함)
 */
async function handleBsSaveConfirm(text) {
  // 저장 버튼이 직접 처리하므로 이 함수는 호출되지 않음
  console.log('⚠️ handleBsSaveConfirm는 더 이상 사용되지 않습니다.');
}

/**
 * 세션 삭제 후 창 닫기 (공통 함수)
 */
async function deleteSessionAndClose() {
  addBsMessage('system', '🗑️ 세션을 삭제하는 중...');
  
  try {
    const response = await fetch(`${API_BASE}/session/${currentSessionId}`, { 
      method: 'DELETE' 
    });
    const data = await response.json();
    
    addBsMessage('system', `✅ ${data.message}`);
    console.log('✅ 세션 삭제 완료:', currentSessionId);
    
    currentSessionId = null;
    
    // 1초 후 창 닫기
    addBsMessage('system', '👋 잠시 후 창이 닫힙니다...');
    
    setTimeout(() => {
      // Electron IPC로 창 닫기 요청
      if (window.require) {
        const { ipcRenderer } = window.require('electron');
        ipcRenderer.send('close-brainstorming-window');
      } else {
        // 일반 브라우저에서는 알림만
        alert('브레인스토밍이 완료되었습니다. 창을 닫아주세요.');
      }
    }, 1000);
    
  } catch (error) {
    console.error('❌ 세션 삭제 실패:', error);
    addBsMessage('system', '❌ 세션 삭제에 실패했습니다. 창을 직접 닫아주세요.');
  }
}

/**
 * 쿠키 가져오기 헬퍼 함수
 */
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

/**
 * 삭제 확인 처리 (아무 키나 누르면 삭제 후 종료)
 */
async function handleBsDeleteConfirm(text) {
  // 아무 키나 눌렀으면 세션 삭제
  addBsMessage('system', '세션을 삭제하는 중...');
  
  try {
    const response = await fetch(`${API_BASE}/session/${currentSessionId}`, { method: 'DELETE' });
    const data = await response.json();
    
    addBsMessage('system', `✅ ${data.message}`);
    
    currentSessionId = null;
    
    // 창 닫기 (IPC로 메인 프로세스에 알림)
    if (window.require) {
      const { ipcRenderer } = window.require('electron');
      setTimeout(() => {
        ipcRenderer.send('close-brainstorming-window');
      }, 1000); // 1초 후 자동 닫기
    }
  } catch (error) {
    console.error('❌ 세션 삭제 실패:', error);
    addBsMessage('system', '❌ 세션 삭제에 실패했습니다. 창을 직접 닫아주세요.');
  }
}

/**
 * 메시지 추가
 */
function addBsMessage(type, text) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `bs-message ${type}`;
  
  const bubble = document.createElement('div');
  bubble.className = 'bs-bubble';
  bubble.textContent = text;
  
  messageDiv.appendChild(bubble);
  bsContent.appendChild(messageDiv);
  
  bsContent.scrollTop = bsContent.scrollHeight;
}

/**
 * 패널 토글
 */
function toggleBsPanel() {
  isBsPanelVisible = !isBsPanelVisible;
  
  if (isBsPanelVisible) {
    bsPanel.style.display = 'flex';
    bsPanel.style.opacity = '1';
    bsPanel.style.transform = 'translate(-50%, -50%)'; // 🔥 중앙 배치 유지
    console.log('👁️ 브레인스토밍 패널 표시');
  } else {
    bsPanel.style.opacity = '0';
    bsPanel.style.transform = 'translate(-50%, -50%) scale(0.95)'; // 🔥 중앙 배치 유지 + 축소 효과
    setTimeout(() => {
      bsPanel.style.display = 'none';
    }, 300);
    console.log('🙈 브레인스토밍 패널 숨김');
  }
}

/**
 * 💾 저장된 아이디어 토글
 */
let isSavedIdeasOpen = false;
let savedIdeasCache = null; // 캐시

async function toggleSavedIdeas() {
  const listContainer = document.getElementById('saved-ideas-list');
  const toggleBtn = document.getElementById('toggle-saved-ideas-btn');
  
  if (!listContainer || !toggleBtn) {
    console.error('❌ 저장된 아이디어 요소를 찾을 수 없습니다.');
    return;
  }
  
  // 이미 열려 있으면 닫기
  if (isSavedIdeasOpen) {
    listContainer.style.display = 'none';
    toggleBtn.textContent = '💾 저장된 아이디어 보기';
    isSavedIdeasOpen = false;
    return;
  }
  
  // 닫혀 있으면 열기
  toggleBtn.textContent = '⏳ 로딩 중...';
  toggleBtn.disabled = true;
  
  try {
    // 캐시가 없으면 API 호출
    if (!savedIdeasCache) {
      const response = await fetch('http://localhost:8000/api/v1/brainstorming/ideas', {
        method: 'GET',
        credentials: 'include'
      });
      
      if (response.status === 401) {
        alert('❌ 로그인이 필요합니다.');
        toggleBtn.textContent = '💾 저장된 아이디어 보기';
        toggleBtn.disabled = false;
        return;
      }
      
      if (!response.ok) {
        throw new Error('아이디어 목록을 가져올 수 없습니다.');
      }
      
      const data = await response.json();
      savedIdeasCache = data.ideas || [];
    }
    
    // 아이디어가 없으면
    if (savedIdeasCache.length === 0) {
      listContainer.innerHTML = `
        <div style="padding: 30px; text-align: center; color: #999;">
          저장된 아이디어가 없습니다.
        </div>
      `;
    } else {
      // 아이디어 목록 렌더링
      renderSavedIdeas(savedIdeasCache);
    }
    
    // 목록 표시
    listContainer.style.display = 'block';
    toggleBtn.textContent = '💾 저장된 아이디어 닫기';
    isSavedIdeasOpen = true;
    
  } catch (error) {
    console.error('❌ 저장된 아이디어 로드 실패:', error);
    alert(`❌ 오류: ${error.message}`);
    toggleBtn.textContent = '💾 저장된 아이디어 보기';
  } finally {
    toggleBtn.disabled = false;
  }
}

/**
 * 저장된 아이디어 목록 렌더링
 */
function renderSavedIdeas(ideas) {
  const listContainer = document.getElementById('saved-ideas-list');
  listContainer.innerHTML = '';
  
  ideas.forEach((idea, index) => {
    // 아이디어 카드
    const ideaCard = document.createElement('div');
    ideaCard.style.cssText = `
      padding: 15px 20px;
      border-bottom: 1px solid #e0e0e0;
      cursor: pointer;
      transition: background 0.2s;
    `;
    
    ideaCard.addEventListener('mouseenter', () => {
      ideaCard.style.background = '#f8f9fa';
    });
    
    ideaCard.addEventListener('mouseleave', () => {
      ideaCard.style.background = 'white';
    });
    
    // 제목
    const title = document.createElement('div');
    title.textContent = `📌 ${idea.title}`;
    title.style.cssText = `
      font-weight: 600;
      font-size: 15px;
      color: #2c3e50;
      margin-bottom: 5px;
    `;
    
    // 날짜
    const date = document.createElement('div');
    date.textContent = new Date(idea.created_at).toLocaleDateString('ko-KR');
    date.style.cssText = `
      font-size: 12px;
      color: #999;
    `;
    
    // 상세 내용 (접힘)
    const detailDiv = document.createElement('div');
    detailDiv.id = `idea-detail-${index}`;
    detailDiv.style.cssText = `
      display: none;
      margin-top: 15px;
      padding: 15px;
      background: #f8f9fa;
      border-radius: 8px;
      max-height: 400px;
      overflow-y: auto;
    `;
    
    // 내용 파싱
    try {
      const descData = JSON.parse(idea.description);
      
      if (descData.ideas && Array.isArray(descData.ideas)) {
        descData.ideas.forEach((ideaItem, i) => {
          const ideaBlock = document.createElement('div');
          ideaBlock.style.cssText = 'margin-bottom: 20px;';
          
          const ideaTitle = document.createElement('h4');
          ideaTitle.textContent = `💡 ${i + 1}. ${ideaItem.title || '제목 없음'}`;
          ideaTitle.style.cssText = 'color: #9CAF88; margin-bottom: 10px; font-size: 14px;';
          
          const ideaDesc = document.createElement('p');
          ideaDesc.textContent = ideaItem.description || '';
          ideaDesc.style.cssText = 'margin-bottom: 10px; font-size: 13px; line-height: 1.6;';
          
          const ideaAnalysis = document.createElement('pre');
          ideaAnalysis.textContent = ideaItem.analysis || '';
          ideaAnalysis.style.cssText = `
            background: white;
            padding: 10px;
            border-radius: 6px;
            white-space: pre-wrap;
            font-family: inherit;
            font-size: 12px;
            line-height: 1.5;
          `;
          
          ideaBlock.appendChild(ideaTitle);
          ideaBlock.appendChild(ideaDesc);
          if (ideaItem.analysis) {
            ideaBlock.appendChild(ideaAnalysis);
          }
          detailDiv.appendChild(ideaBlock);
        });
      } else {
        detailDiv.textContent = idea.description;
      }
    } catch {
      detailDiv.textContent = idea.description;
      detailDiv.style.whiteSpace = 'pre-wrap';
      detailDiv.style.fontSize = '13px';
    }
    
    // 클릭 시 토글
    ideaCard.addEventListener('click', () => {
      const isOpen = detailDiv.style.display === 'block';
      detailDiv.style.display = isOpen ? 'none' : 'block';
    });
    
    ideaCard.appendChild(title);
    ideaCard.appendChild(date);
    ideaCard.appendChild(detailDiv);
    listContainer.appendChild(ideaCard);
  });
}

/**
 * 저장 후 캐시 갱신
 */
export function refreshSavedIdeasCache() {
  savedIdeasCache = null;
  console.log('🔄 저장된 아이디어 캐시 갱신');
}
