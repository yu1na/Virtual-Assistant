/**
 * 일반 채팅 UI 관리
 * 간단한 대화 및 기타 기능
 */

import { sendMultiAgentMessage, initChatbotService } from "./chatbotService.js";

/**
 * 쿠키에서 값 가져오기
 */
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// 쿠키에서 토큰 가져와서 챗봇 서비스 초기화 (BrowserWindow 간 공유됨)
console.log('🍪 [DEBUG] 전체 쿠키:', document.cookie);
console.log('🍪 [DEBUG] 쿠키 길이:', document.cookie.length);

const accessToken = getCookie('access_token');
console.log('🍪 쿠키에서 토큰 확인:', {
  accessToken: accessToken ? `${accessToken.substring(0, 20)}...` : 'null'
});

// 모든 쿠키 이름 출력
const allCookies = document.cookie.split(';').map(c => c.trim().split('=')[0]);
console.log('🍪 [DEBUG] 사용 가능한 쿠키 이름들:', allCookies);

if (accessToken) {
  initChatbotService(accessToken);
  console.log('✅ 쿠키에서 액세스 토큰 로드 완료');
} else {
  console.warn(
    "⚠️ 액세스 토큰이 없습니다. 일부 기능(메일 전송 등)은 로그인이 필요합니다."
  );
}

let messages = [];
let isPanelVisible = true;
let chatPanel = null;
let messagesContainer = null;
let chatInput = null;
let sendBtn = null;
let isChatPanelInitialized = false;
let userDisplayEl = null;

/**
 * 채팅 패널 초기화
 */
export function initChatPanel() {
  if (isChatPanelInitialized) {
    console.log("⚠️  채팅 패널 이미 초기화됨 - 스킵");
    return;
  }

  console.log('💬 채팅 패널 초기화 중...');

  chatPanel = document.getElementById('chat-panel');
  messagesContainer = document.getElementById('messages');
  chatInput = document.getElementById('chat-input');
  sendBtn = document.getElementById('send-btn');
  userDisplayEl = document.getElementById('user-display');

  // 사용자 표시 숨기기 (보고서 기능에서만 사용자 이름 필요)
  if (userDisplayEl) {
    userDisplayEl.style.display = "none";
  }

  if (!chatPanel || !messagesContainer || !chatInput || !sendBtn) {
    console.error("❌ 채팅 패널 요소를 찾을 수 없습니다.");
    return;
  }

  // 초기 메시지 추가
  addMessage("assistant", "안녕하세요! 무엇을 도와드릴까요? 😊");

  // 이벤트 리스너 등록
  sendBtn.addEventListener("click", handleSendMessage);
  chatInput.addEventListener("keydown", handleChatInputKeydown);
  window.addEventListener("keydown", handleGlobalKeydown);

  // 드래그 앤 드롭 기능 초기화
  initDragAndDrop();

  // 리사이즈 기능 초기화
  initResize();

  isChatPanelInitialized = true;

  console.log("✅ 채팅 패널 초기화 완료");
}

/**
 * 드래그 앤 드롭 기능 초기화
 */
function initDragAndDrop() {
  const header = chatPanel.querySelector("h2");
  if (!header) return;

  let isDragging = false;
  let startX = 0;
  let startY = 0;
  let initialLeft = 0;
  let initialTop = 0;

  // 헤더에 드래그 커서 추가
  header.style.cursor = "move";
  header.style.userSelect = "none";

  header.addEventListener("mousedown", (e) => {
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;

    // 현재 위치 가져오기
    const rect = chatPanel.getBoundingClientRect();
    initialLeft = rect.left;
    initialTop = rect.top;

    chatPanel.style.transition = "none";
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;

    const deltaX = e.clientX - startX;
    const deltaY = e.clientY - startY;

    const newLeft = initialLeft + deltaX;
    const newTop = initialTop + deltaY;

    // 화면 밖으로 나가지 않도록 제한
    const maxLeft = window.innerWidth - chatPanel.offsetWidth;
    const maxTop = window.innerHeight - chatPanel.offsetHeight;

    chatPanel.style.left = Math.max(0, Math.min(newLeft, maxLeft)) + "px";
    chatPanel.style.top = Math.max(0, Math.min(newTop, maxTop)) + "px";
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      chatPanel.style.transition = "";
    }
  });

  console.log("✅ 드래그 앤 드롭 기능 초기화 완료");
}

/**
 * 리사이즈 기능 초기화
 */
function initResize() {
  // 리사이즈 핸들 생성
  const resizeHandle = document.createElement("div");
  resizeHandle.className = "resize-handle";
  resizeHandle.innerHTML = "⋰";
  chatPanel.appendChild(resizeHandle);

  let isResizing = false;
  let startX = 0;
  let startY = 0;
  let startWidth = 0;
  let startHeight = 0;

  resizeHandle.addEventListener("mousedown", (e) => {
    isResizing = true;
    startX = e.clientX;
    startY = e.clientY;

    const rect = chatPanel.getBoundingClientRect();
    startWidth = rect.width;
    startHeight = rect.height;

    chatPanel.style.transition = "none";
    e.preventDefault();
    e.stopPropagation();
  });

  document.addEventListener("mousemove", (e) => {
    if (!isResizing) return;

    const deltaX = e.clientX - startX;
    const deltaY = e.clientY - startY;

    const newWidth = startWidth + deltaX;
    const newHeight = startHeight + deltaY;

    // 최소/최대 크기 제한
    const minWidth = 300;
    const maxWidth = 800;
    const minHeight = 400;
    const maxHeight = window.innerHeight - 100;

    chatPanel.style.width =
      Math.max(minWidth, Math.min(newWidth, maxWidth)) + "px";
    chatPanel.style.height =
      Math.max(minHeight, Math.min(newHeight, maxHeight)) + "px";
  });

  document.addEventListener("mouseup", () => {
    if (isResizing) {
      isResizing = false;
      chatPanel.style.transition = "";
    }
  });

  console.log("✅ 리사이즈 기능 초기화 완료");
}

// 전역으로 export
window.initChatPanel = initChatPanel;
window.addMessage = addMessage;

/**
 * 채팅 입력창 키 이벤트
 */
function handleChatInputKeydown(e) {
  if (e.isComposing || e.keyCode === 229) {
    return;
  }

  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSendMessage();
  }
}

/**
 * 전역 키 이벤트 (패널 토글 및 캐릭터 토글)
 */
function handleGlobalKeydown(e) {
  // Shift + Ctrl(Cmd) + Enter: 캐릭터 토글
  if (e.shiftKey && (e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    toggleCharacter();
    return;
  }

  // Ctrl(Cmd) + Enter: 챗창 토글
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    togglePanel();
  }
}

/**
 * 메시지 전송 처리
 */
async function handleSendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  if (sendBtn.disabled) {
    console.log("⚠️  이미 전송 중...");
    return;
  }

  addMessage("user", text);

  chatInput.value = "";
  chatInput.blur();
  setTimeout(() => chatInput.focus(), 0);

  sendBtn.disabled = true;
  sendBtn.textContent = "...";

  try {
    // 모든 메시지를 Multi-Agent Supervisor로 전달 (자동 라우팅)
    // 키워드 기반 하드코딩 제거: 백엔드 인텐트 분류에 맡김
    const result = await sendMultiAgentMessage(text);

    // HR(RAG), Notion, Insurance 에이전트인 경우 마크다운 렌더링 적용
    const isMarkdown = (result.agent_used === 'rag' || result.agent_used === 'rag_tool' || result.agent_used === 'notion_agent' || result.agent_used === 'insurance' || result.agent_used === 'insurance_tool');

    // 사용된 에이전트 로그
    if (result.agent_used) {
      console.log(`🤖 사용된 에이전트: ${result.agent_used}`);
    }


    // Intent 기준 UI 분기 (백엔드 응답 기반)
    const intent = result.intent;
    const agent = result.agent_used;
    let answer = result.answer;

    // 디버깅: 응답 내용 확인
    console.log("[DEBUG] 프론트엔드 응답 확인:", {
      intent,
      agent,
      answer_preview: answer ? answer.substring(0, 100) : "null",
      has_marker: answer ? answer.includes("__INTENT_LOOKUP__") : false,
    });

    // report_tool이 lookup intent를 처리한 경우 감지 (특수 마커)
    // agent가 'report' 또는 'report_tool'이고, answer에 마커가 있으면 RAG 응답으로 처리
    if ((agent === "report" || agent === "report_tool") && answer) {
      if (answer.includes("__INTENT_LOOKUP__")) {
        // lookup intent인 경우: 마커 제거하고 RAG 응답으로 처리
        answer = answer.replace("__INTENT_LOOKUP__", "");
        console.log("[DEBUG] ✅ RAG 응답으로 처리 (마커 감지됨)");
        // RAG 응답이므로 마크다운 렌더링 적용
        addMessage("assistant", answer, true); // isMarkdown = true
        return;
      }
      // 마커가 없으면 보고서 도구 버튼 표시 (아래 조건문에서 처리)
    }

    // 1. RAG(intent === 'lookup' 또는 'rag') 또는 insurance이면 → LLM 응답만 보여주고 종료
    if (intent === "lookup" || intent === "rag" || agent === "insurance_tool" || agent === "insurance") {
      console.log(`📝 [Insurance/RAG 디버깅] Markdown: ${isMarkdown}, Agent: ${agent}, Intent: ${intent}`);
      console.log(`📝 [Insurance/RAG 디버깅] Answer 샘플: ${answer ? answer.substring(0, 200) : 'null'}`);
      addMessage("assistant", answer, isMarkdown);
      return;
    }

    // 2. Planning(intent === 'planning')이면 → 업무 카드 UI 표시
    if (
      intent === "planning" ||
      agent === "planning" ||
      agent === "planning_tool"
    ) {
      await loadAndDisplayTaskCardsInChat();
      return;
    }

    // 3. 보고서 작성(intent === 'report')이면 → 보고서 도구 열기 버튼만 제공
    if (
      intent === "report" ||
      intent === "report_write" ||
      agent === "report" ||
      agent === "report_tool"
    ) {
      addMessage("assistant", "네 보고서 작성 기능을 도와드리겠습니다!");
      addConfirmationButton("📝 보고서 도구 열기", () => {
        openReportPopup();
        addMessage("assistant", "보고서 도구를 열었습니다! 📝");
      });
      return;
    }


    // 브레인스토밍 에이전트가 사용되었으면
    if (
      result.agent_used === "brainstorming" ||
      result.agent_used === "brainstorming_tool"
    ) {
      addMessage("assistant", result.answer);

      // 1. "SUGGESTION:"으로 시작하면 (제안 모드)
      if (result.answer.includes("SUGGESTION:")) {
        const cleanMessage = result.answer.replace("SUGGESTION:", "").trim();
        // 메시지는 이미 addMessage로 출력되었으므로 버튼만 추가
        addBrainstormingButtons();
      }
      // 2. 그 외 (RAG 답변 등) - 자동 실행하지 않고 버튼 표시
      else {
        addBrainstormingButtons();
      }
      return;
    }


    // 그 외 일반 에이전트
    console.log(`📝 일반 에이전트 응답 - Markdown: ${isMarkdown}, Agent: ${agent}`);
    addMessage("assistant", result.answer, isMarkdown);
  } catch (error) {
    console.error("❌ 채팅 오류:", error);
    addMessage("assistant", "죄송합니다. 오류가 발생했습니다. 😢");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "전송";
  }
}

/**
 * 메인 챗봇에서 업무 카드 UI 로드 및 표시
 */
async function loadAndDisplayTaskCardsInChat() {
  try {
    // taskUI.js의 함수들을 동적으로 import
    const { addTaskRecommendations } = await import('../report/taskUI.js');
    const { getTodayPlan } = await import('../report/taskService.js');

    const planResult = await getTodayPlan();

    if (planResult.type === 'task_recommendations' && planResult.data.tasks && planResult.data.tasks.length > 0) {
      addTaskRecommendations(
        planResult.data,
        addMessage,
        messagesContainer
      );
    } else {
      addMessage("assistant", "추천할 업무가 없습니다. 직접 작성해주세요! 😊");
    }
  } catch (error) {
    console.error("❌ 업무 카드 로드 오류:", error);
    addMessage(
      "assistant",
      `업무 카드를 불러오는 중 오류가 발생했습니다. 😢\n${error.message || ""}`
    );
  }
}

/**
 * 간단한 응답 처리
 */
async function handleSimpleResponse(text) {
  const lower = text.toLowerCase();

  // 브레인스토밍 안내
  if (lower.includes("브레인") || lower.includes("아이디어")) {
    addMessage(
      "assistant",
      "브레인스토밍은 **Ctrl+Shift+B**를 눌러\n브레인스토밍 패널을 열어주세요! 💡"
    );
    return;
  }

  // 일반 응답
  addMessage(
    "assistant",
    `"${text}" - 답변을 준비 중입니다! 😊\n\n사용 가능한 기능:\n• Ctrl+Shift+B - 브레인스토밍`
  );
}

/**
 * 메시지 추가
 */
function addMessage(role, text, isMarkdown = false) {
  // 메시지 객체에 에이전트 정보 포함
  const messageObj = {
    role,
    content: text,
  };

  messages.push(messageObj);

  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  // 마크다운 렌더링 (HR RAG 등)
  if (isMarkdown && role === "assistant" && typeof marked !== "undefined") {
    console.log(`🎨 [마크다운 렌더링] isMarkdown=${isMarkdown}, marked 존재=${typeof marked !== "undefined"}`);
    // marked.js 버전 호환성 처리
    if (typeof marked.parse === "function") {
      bubble.innerHTML = marked.parse(text);
      console.log(`✅ [마크다운] marked.parse() 사용`);
    } else if (typeof marked === "function") {
      bubble.innerHTML = marked(text);
      console.log(`✅ [마크다운] marked() 사용`);
    } else {
      bubble.textContent = text;
      console.log(`⚠️ [마크다운] marked 함수 없음 - 일반 텍스트`);
    }
  } else {
    bubble.textContent = text;
    console.log(`📄 [일반 텍스트] isMarkdown=${isMarkdown}, role=${role}, marked=${typeof marked}`);
  }

  messageDiv.appendChild(bubble);
  messagesContainer.appendChild(messageDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  console.log(
    `💬 [${role}]: ${text.substring(0, 50)}${text.length > 50 ? "..." : ""}`
  );
}

/**
 * 확인 버튼 추가
 */
function addConfirmationButton(text, onClick) {
  const buttonDiv = document.createElement("div");
  buttonDiv.className = "message assistant"; // 챗봇 메시지처럼 보이게

  const button = document.createElement("button");
  button.textContent = text;
  button.style.cssText = `
    background: #9CAF88;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 14px;
    margin-top: 5px;
    transition: all 0.2s;
  `;

  button.addEventListener("mouseover", () => {
    button.style.transform = "scale(1.05)";
    button.style.background = "#7A8C6F";
  });

  button.addEventListener("mouseout", () => {
    button.style.transform = "scale(1)";
    button.style.background = "#9CAF88";
  });

  button.addEventListener("click", () => {
    onClick();
    button.disabled = true;
    button.style.opacity = "0.7";
    button.style.cursor = "default";
    button.textContent = "✅ " + text;
  });

  buttonDiv.appendChild(button);
  messagesContainer.appendChild(buttonDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * 브레인스토밍 버튼 추가 (시작하기만)
 */
function addBrainstormingButtons() {
  const buttonContainer = document.createElement("div");
  buttonContainer.className = "message assistant";
  buttonContainer.style.cssText = `
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    align-items: center;
  `;

  // 브레인스토밍 시작 버튼
  const startBtn = document.createElement("button");
  startBtn.textContent = "🚀 브레인스토밍 시작";
  startBtn.style.cssText = `
    background: #9CAF88;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  `;

  startBtn.addEventListener("mouseover", () => {
    startBtn.style.transform = "scale(1.05)";
    startBtn.style.background = "#7A8C6F";
  });

  startBtn.addEventListener("mouseout", () => {
    startBtn.style.transform = "scale(1)";
    startBtn.style.background = "#9CAF88";
  });

  startBtn.addEventListener("click", () => {
    openBrainstormingPopup();
    addMessage("assistant", "브레인스토밍을 시작합니다! 🚀");
    startBtn.disabled = true;
    startBtn.style.opacity = "0.7";
  });

  buttonContainer.appendChild(startBtn);
  messagesContainer.appendChild(buttonContainer);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * 선택 버튼 추가 (수락/거절)
 */
function addChoiceButtons(acceptText, declineText, onAccept, onDecline) {
  const buttonDiv = document.createElement("div");
  buttonDiv.className = "message assistant";
  buttonDiv.style.display = "flex";
  buttonDiv.style.gap = "10px";

  // 수락 버튼
  const acceptBtn = document.createElement("button");
  acceptBtn.textContent = acceptText;
  acceptBtn.style.cssText = `
    background: #9CAF88;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  `;

  // 거절 버튼
  const declineBtn = document.createElement("button");
  declineBtn.textContent = declineText;
  declineBtn.style.cssText = `
    background: #e0e0e0;
    color: #555;
    border: none;
    padding: 8px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  `;

  // 호버 효과
  acceptBtn.onmouseover = () => {
    acceptBtn.style.transform = "scale(1.05)";
    acceptBtn.style.background = "#7A8C6F";
  };
  acceptBtn.onmouseout = () => {
    acceptBtn.style.transform = "scale(1)";
    acceptBtn.style.background = "#9CAF88";
  };

  declineBtn.onmouseover = () => {
    declineBtn.style.transform = "scale(1.05)";
    declineBtn.style.background = "#d0d0d0";
  };
  declineBtn.onmouseout = () => {
    declineBtn.style.transform = "scale(1)";
    declineBtn.style.background = "#e0e0e0";
  };

  // 클릭 이벤트
  acceptBtn.onclick = () => {
    onAccept();
    disableButtons();
  };

  declineBtn.onclick = () => {
    onDecline();
    disableButtons();
  };

  function disableButtons() {
    acceptBtn.disabled = true;
    declineBtn.disabled = true;
    acceptBtn.style.opacity = "0.7";
    declineBtn.style.opacity = "0.7";
    acceptBtn.style.cursor = "default";
    declineBtn.style.cursor = "default";
  }

  buttonDiv.appendChild(acceptBtn);
  buttonDiv.appendChild(declineBtn);
  messagesContainer.appendChild(buttonDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * 패널 토글
 */
function togglePanel() {
  isPanelVisible = !isPanelVisible;

  if (isPanelVisible) {
    chatPanel.style.display = "flex";
    console.log("👁️ 채팅 패널 표시");
  } else {
    chatPanel.style.display = "none";
    console.log("🙈 채팅 패널 숨김");
  }
}

/**
 * 캐릭터 토글 (Shift + Ctrl/Cmd + Enter)
 */
let isCharacterVisible = true;
function toggleCharacter() {
  const stage = document.getElementById("stage");
  if (!stage) {
    console.warn("⚠️  Live2D stage 요소를 찾을 수 없습니다.");
    return;
  }

  isCharacterVisible = !isCharacterVisible;

  if (isCharacterVisible) {
    // display 속성을 제거하여 원래대로 복원
    stage.style.display = "";
    console.log("👁️ 캐릭터 표시");
    addMessage("assistant", "안녕하세요! 다시 왔어요! 👋");
  } else {
    stage.style.display = "none";
    console.log("🙈 캐릭터 숨김");
    addMessage(
      "assistant",
      "잠시 숨을게요~ Shift + Ctrl/Cmd + Enter로 다시 불러주세요! 👻"
    );
  }
}

/**
 * 브레인스토밍 팝업 열기
 */
function openBrainstormingPopup() {
  console.log("🧠 브레인스토밍 팝업 열기");

  // Electron IPC로 메인 프로세스에 팝업 요청
  if (window.require) {
    const { ipcRenderer } = window.require("electron");
    ipcRenderer.send("open-brainstorming-popup");

    // 챗봇 패널 숨기기
    chatPanel.style.display = "none";
    isPanelVisible = false;

    // 팝업 종료 이벤트 리스너
    ipcRenderer.once("brainstorming-closed", (event, data) => {
      console.log("🧠 브레인스토밍 완료:", data);

      // 챗봇 패널 복구
      chatPanel.style.display = "flex";
      isPanelVisible = true;

      // 완료 메시지 추가
      addMessage("assistant", "브레인스토밍이 종료되었습니다.");
    });
  } else {
    console.error("❌ Electron IPC를 사용할 수 없습니다.");
    addMessage("assistant", "❌ 브레인스토밍 팝업을 열 수 없습니다.");
  }
}

/**
 * 보고서 팝업 열기
 */
function openReportPopup() {
  console.log("📝 보고서 팝업 열기");

  // Electron IPC로 메인 프로세스에 팝업 요청
  if (window.require) {
    const { ipcRenderer } = window.require("electron");
    ipcRenderer.send("open-report-popup");

    // 챗봇 패널 숨기기
    chatPanel.style.display = "none";
    isPanelVisible = false;

    // 팝업 종료 이벤트 리스너
    ipcRenderer.once("report-closed", (event, data) => {
      console.log("📝 보고서 팝업 완료:", data);

      // 챗봇 패널 복구
      chatPanel.style.display = "flex";
      isPanelVisible = true;

      // 완료 메시지 추가
      addMessage("assistant", "보고서 작성이 종료되었습니다.");
    });
  } else {
    console.error("❌ Electron IPC를 사용할 수 없습니다.");
    addMessage("assistant", "❌ 보고서 팝업을 열 수 없습니다.");
  }
}

/**
 * 메시지 히스토리 가져오기 (Notion Agent가 사용)
 */
window.getMessages = function () {
  return messages;
};
