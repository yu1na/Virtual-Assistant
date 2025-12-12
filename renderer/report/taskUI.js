/**
 * 추천 업무 UI 관리
 * 
 * 구조:
 * 1. 요약은 일반 bubble 메시지로 표시
 * 2. 추천 UI는 .no-bubble로 독립 렌더링
 *    - 안내 문구
 *    - "직접 작성하기" 버튼
 *    - 250px 스크롤 카드 리스트
 *    - "선택 완료" 버튼
 */

import { saveSelectedTasks } from './taskService.js';

// 전역 폰트 설정 (모든 동적 생성 요소에 적용)
const DEFAULT_FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

// 추천 업무 선택 상태
let selectedTasks = new Set();
let currentRecommendation = null;
let customTasks = []; // 직접 작성한 업무 목록 (최대 3개)
const MAX_SELECTED_TASKS = 3; // 최대 선택 가능한 업무 수
const MAX_CUSTOM_TASKS = 3; // 최대 직접 작성 가능한 업무 수

/**
 * 추천 업무 UI 표시 (bubble 밖 독립 렌더링)
 */
export function addTaskRecommendations(data, addMessage, messagesContainer) {
  console.log('🔥 [TaskUI] addTaskRecommendations 호출:', data);
  
  const { tasks, summary, owner_id, target_date, task_sources } = data;
  const safeOwnerId = owner_id || null;
  const safeTargetDate = target_date || new Date().toISOString().split('T')[0];
  
  // 이전 상태 초기화 (Intent 고착 방지)
  resetTaskState();
  
  currentRecommendation = { owner_id: safeOwnerId, target_date: safeTargetDate, tasks };
  
  // 1) 요약은 일반 bubble 메시지로 표시
  addMessage('assistant', summary || '오늘의 추천 업무입니다!');
  
  // 2) 추천 UI는 bubble 밖 독립 메시지로 표시
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message assistant no-bubble';
  
  const container = document.createElement('div');
  container.className = 'task-recommendations-container';
  
  // 안내 문구
  const guideDiv = document.createElement('div');
  guideDiv.className = 'task-guide';
  guideDiv.textContent = '📌 수행할 업무를 선택하거나 직접 입력해주세요';
  container.appendChild(guideDiv);
  
  // 직접 작성하기 버튼 (카드 리스트 위) - 보고서 팝업 스타일 적용
  const customTaskButton = document.createElement('button');
  customTaskButton.className = 'task-custom-button';
  customTaskButton.textContent = '✏️ 직접 작성하기';
  customTaskButton.style.cssText = `
    width: 100%;
    padding: 12px 20px;
    border: 2px solid #fdbc66;
    border-radius: 8px;
    background: white;
    color: #fdbc66;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 12px;
  `;
  customTaskButton.addEventListener('mouseenter', () => {
    customTaskButton.style.background = '#fdbc66';
    customTaskButton.style.color = 'white';
  });
  customTaskButton.addEventListener('mouseleave', () => {
    customTaskButton.style.background = 'white';
    customTaskButton.style.color = '#fdbc66';
  });
  customTaskButton.addEventListener('click', () => {
    console.log('🔥 [TaskUI] 직접 작성하기 버튼 클릭');
    showCustomTaskInput(safeOwnerId, safeTargetDate, addMessage);
  });
  container.appendChild(customTaskButton);
  
  // 카드 리스트 (스크롤 영역)
  const cardsContainer = document.createElement('div');
  cardsContainer.className = 'task-cards';
  
  tasks.forEach((task, index) => {
    const card = createTaskCard(task, index, container, task_sources);
    cardsContainer.appendChild(card);
  });
  
  container.appendChild(cardsContainer);
  
  // 선택 완료 버튼
  const saveButton = document.createElement('button');
  saveButton.className = 'task-save-button';
  saveButton.textContent = '선택 완료';
  saveButton.disabled = true;
  saveButton.addEventListener('click', (e) => {
    handleSaveSelectedTasks(e, addMessage, messagesContainer);
  });
  container.appendChild(saveButton);
  
  // 초기 선택 개수 표시
  updateSelectionCount(container, customTasks.length);
  
  messageDiv.appendChild(container);
  messagesContainer.appendChild(messageDiv);
  
  // 스크롤
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  
  console.log(`✅ [TaskUI] 추천 업무 ${tasks.length}개 표시 완료`);
}

/**
 * 업무 카드 생성
 */
function createTaskCard(task, index, container, task_sources) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.dataset.index = index;
  
  const priorityBadge = document.createElement('span');
  priorityBadge.className = `priority-badge priority-${task.priority}`;
  priorityBadge.textContent = {
    high: '높음',
    medium: '보통',
    low: '낮음'
  }[task.priority] || '보통';
  
  const title = document.createElement('div');
  title.className = 'task-title';
  title.textContent = task.title;
  
  const description = document.createElement('div');
  description.className = 'task-description';
  description.textContent = task.description;
  
  const meta = document.createElement('div');
  meta.className = 'task-meta';
  meta.innerHTML = `
    <span class="task-category">📁 ${task.category}</span>
    <span class="task-time">⏰ ${task.expected_time}</span>
  `;
  
  // 데이터 출처 표시 추가
  const sourceInfo = document.createElement('div');
  sourceInfo.className = 'task-source';
  sourceInfo.style.cssText = `
    font-size: 11px;
    color: #888;
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px solid #eee;
  `;
  
  if (task_sources && task_sources.length > 0) {
    const source = task_sources.find(s => s.task_index === index);
    if (source) {
      sourceInfo.textContent = `📌 ${source.source_description}`;
    } else {
      sourceInfo.textContent = '📌 맞춤형 추천 업무(ChromaDB 접근)';
    }
  } else {
    sourceInfo.textContent = '📌 맞춤형 추천 업무(ChromaDB 접근)';
  }
  
  card.appendChild(priorityBadge);
  card.appendChild(title);
  card.appendChild(description);
  card.appendChild(meta);
  card.appendChild(sourceInfo);
  
  // 카드 클릭 이벤트 (이벤트 전파 방지)
  card.style.cursor = 'pointer';
  card.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleTaskSelection(card, index, container);
  });
  
  return card;
}

/**
 * 업무 선택 토글 (최대 3개까지)
 */
function toggleTaskSelection(card, index, container) {
  if (selectedTasks.has(index)) {
    // 선택 해제
    selectedTasks.delete(index);
    card.classList.remove('selected');
  } else {
    // 최대 3개까지만 선택 가능
    const totalSelected = selectedTasks.size + customTasks.length;
    if (totalSelected >= MAX_SELECTED_TASKS) {
      alert(`최대 ${MAX_SELECTED_TASKS}개의 업무만 선택할 수 있습니다.`);
      return;
    }
    
    selectedTasks.add(index);
    card.classList.add('selected');
  }
  
  const saveButton = container.querySelector('.task-save-button');
  if (saveButton) {
    const totalSelected = selectedTasks.size + customTasks.length;
    saveButton.disabled = totalSelected === 0;
    // 선택 개수 표시 업데이트
    updateSelectionCount(container, totalSelected);
  }
  
  console.log(`✅ [TaskUI] 선택된 업무: ${selectedTasks.size}개 (직접 작성: ${customTasks.length}개)`);
}

/**
 * 선택 개수 표시 업데이트
 */
function updateSelectionCount(container, totalCount) {
  let countDisplay = container.querySelector('.selection-count');
  if (!countDisplay) {
    countDisplay = document.createElement('div');
    countDisplay.className = 'selection-count';
    countDisplay.style.cssText = `
      text-align: center;
      margin-bottom: 8px;
      font-size: 13px;
      color: #666;
      font-weight: 500;
    `;
    const saveButton = container.querySelector('.task-save-button');
    if (saveButton) {
      saveButton.parentNode.insertBefore(countDisplay, saveButton);
    }
  }
  
  if (totalCount > 0) {
    countDisplay.textContent = `선택된 업무: ${totalCount}/${MAX_SELECTED_TASKS}개`;
    countDisplay.style.color = totalCount >= MAX_SELECTED_TASKS ? '#fdbc66' : '#666';
  } else {
    countDisplay.textContent = '';
  }
}

/**
 * 선택한 업무 저장 (재확인 후 저장)
 */
async function handleSaveSelectedTasks(event, addMessage, messagesContainer) {
  if (!currentRecommendation) {
    return;
  }
  
  const { owner_id, target_date, tasks } = currentRecommendation;
  const selectedTasksList = Array.from(selectedTasks).map(i => tasks[i]);
  const allTasksToSave = [...selectedTasksList, ...customTasks];
  
  if (allTasksToSave.length === 0) {
    alert('최소 1개 이상의 업무를 선택해주세요.');
    return;
  }
  
  // 재확인 질문 표시
  const confirmationMessage = createConfirmationMessage(allTasksToSave);
  addMessage('assistant', confirmationMessage);
  
  // 확인/취소 버튼 추가
  const confirmDiv = document.createElement('div');
  confirmDiv.className = 'message assistant';
  confirmDiv.style.cssText = 'margin-top: 12px;';
  
  const confirmBtn = document.createElement('button');
  confirmBtn.textContent = '✅ 맞습니다';
  confirmBtn.style.cssText = `
    background: #fdbc66;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    margin-right: 10px;
    transition: all 0.2s;
  `;
  confirmBtn.addEventListener('mouseenter', () => {
    confirmBtn.style.background = '#f0a850';
  });
  confirmBtn.addEventListener('mouseleave', () => {
    confirmBtn.style.background = '#fdbc66';
  });
  
  const cancelBtn = document.createElement('button');
  cancelBtn.textContent = '❌ 취소';
  cancelBtn.style.cssText = `
    background: white;
    color: #d4a574;
    border: 2px solid #d4a574;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  `;
  cancelBtn.addEventListener('mouseenter', () => {
    cancelBtn.style.background = '#f5f5f5';
  });
  cancelBtn.addEventListener('mouseleave', () => {
    cancelBtn.style.background = 'white';
  });
  
  confirmBtn.addEventListener('click', async () => {
    confirmDiv.remove();
    await saveTasks(owner_id, target_date, allTasksToSave, addMessage);
  });
  
  cancelBtn.addEventListener('click', () => {
    confirmDiv.remove();
    
    // 취소 시 UI 초기화: 선택된 카드 스타일 제거 및 상태 초기화
    const allCards = document.querySelectorAll('.task-card.selected');
    allCards.forEach(card => {
      card.classList.remove('selected');
    });
    
    // 상태 초기화 (직접 작성하기 모드 정상 동작을 위해)
    resetTaskState();
    
    // 선택 완료 버튼 비활성화 및 카운트 업데이트
    const container = document.querySelector('.task-recommendations-container');
    if (container) {
      const saveButton = container.querySelector('.task-save-button');
      if (saveButton) {
        saveButton.disabled = true;
      }
      updateSelectionCount(container, 0);
    }
    
    addMessage('assistant', '업무 선택이 취소되었습니다. 다시 선택해주세요.');
  });
  
  confirmDiv.appendChild(confirmBtn);
  confirmDiv.appendChild(cancelBtn);
  
  // messagesContainer가 파라미터로 전달되지 않으면 자동으로 찾기 (하위 호환성)
  if (!messagesContainer) {
    messagesContainer = document.getElementById('report-messages') || document.getElementById('messages');
  }
  
  if (messagesContainer) {
    messagesContainer.appendChild(confirmDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

/**
 * 재확인 메시지 생성
 */
function createConfirmationMessage(tasks) {
  let message = '선택한 업무는 다음과 같습니다:\n\n';
  tasks.forEach((task, index) => {
    message += `${index + 1}. ${task.title}\n`;
  });
  message += '\n맞습니까?';
  return message;
}

/**
 * 실제 업무 저장
 */
async function saveTasks(ownerId, targetDate, tasksToSave, addMessage) {
  try {
    // 최대 3개까지만 저장
    if (tasksToSave.length > 3) {
      addMessage('assistant', '⚠️ 금일 진행 업무는 최대 3개까지만 저장할 수 있습니다. 처음 3개만 저장됩니다.');
      tasksToSave = tasksToSave.slice(0, 3);
    }
    
    // 항상 덮어쓰기 (append: false)
    const result = await saveSelectedTasks(ownerId, targetDate, tasksToSave, false);
    
    if (result.success) {
      addMessage('assistant', `✅ ${result.saved_count}개의 업무가 금일 진행 업무로 저장되었습니다!`);
      
      // 상태 초기화 (Intent 고착 방지)
      resetTaskState();
      
      const saveButton = document.querySelector('.task-save-button');
      if (saveButton) {
        saveButton.closest('.task-recommendations-container').style.opacity = '0.5';
        saveButton.textContent = '저장 완료';
        saveButton.disabled = true;
      }
      
      console.log('✅ [TaskUI] 업무 저장 완료 & 상태 초기화');
    } else {
      addMessage('assistant', `❌ 저장 실패: ${result.message}`);
    }
  } catch (error) {
    console.error('❌ [TaskUI] 저장 오류:', error);
    addMessage('assistant', '❌ 업무 저장 중 오류가 발생했습니다.');
  }
}

/**
 * 직접 작성하기 모달 표시
 */
export function showCustomTaskInput(ownerId, targetDate, addMessage) {
  console.log('🔥 [TaskUI] 직접 작성하기 모달 표시');
  
  const existingModal = document.querySelector('.custom-task-modal');
  if (existingModal) existingModal.remove();
  
  const modal = document.createElement('div');
  modal.className = 'custom-task-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  `;
  
  const modalContent = document.createElement('div');
  modalContent.className = 'custom-task-modal-content';
  modalContent.style.cssText = `
    background: white;
    border-radius: 12px;
    padding: 24px;
    width: 100%;
    max-width: 500px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    animation: modalSlideIn 0.3s ease-out;
  `;
  
  // 애니메이션 추가
  const style = document.createElement('style');
  style.textContent = `
    @keyframes modalSlideIn {
      from {
        opacity: 0;
        transform: translateY(-20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
  `;
  document.head.appendChild(style);
  
  const title = document.createElement('h3');
  title.textContent = '✏️ 직접 업무 작성하기';
  title.style.cssText = `margin: 0 0 20px 0; color: #333; font-size: 18px; font-weight: 600;`;
  
  const label = document.createElement('label');
  label.textContent = '업무 내용을 입력해주세요:';
  label.style.cssText = `display: block; margin-bottom: 8px; color: #555; font-size: 14px; font-weight: 500;`;
  
  const textarea = document.createElement('textarea');
  textarea.className = 'custom-task-input';
  textarea.placeholder = '예: 4주차 상담 일정 정리';
  textarea.rows = 4;
  textarea.style.cssText = `
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 14px;
    resize: vertical;
    box-sizing: border-box;
    transition: border-color 0.2s;
  `;
  textarea.addEventListener('focus', () => {
    textarea.style.borderColor = '#fdbc66';
    textarea.style.outline = 'none';
    textarea.style.boxShadow = '0 0 0 2px rgba(253, 188, 102, 0.2)';
  });
  textarea.addEventListener('blur', () => {
    textarea.style.borderColor = '#e0e0e0';
    textarea.style.boxShadow = 'none';
  });
  
  const btnWrap = document.createElement('div');
  btnWrap.style.cssText = 'display: flex; gap: 10px; margin-top: 20px;';
  
  const saveBtn = document.createElement('button');
  saveBtn.className = 'custom-task-save-btn';
  saveBtn.textContent = '저장';
  saveBtn.style.cssText = `
    flex: 1;
    padding: 12px;
    border: none;
    border-radius: 8px;
    background: #fdbc66;
    color: white;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  `;
  saveBtn.addEventListener('mouseenter', () => {
    saveBtn.style.background = '#f0a850';
    saveBtn.style.transform = 'translateY(-1px)';
  });
  saveBtn.addEventListener('mouseleave', () => {
    saveBtn.style.background = '#fdbc66';
    saveBtn.style.transform = 'translateY(0)';
  });
  
  const cancelBtn = document.createElement('button');
  cancelBtn.textContent = '취소';
  cancelBtn.style.cssText = `
    flex: 1;
    padding: 12px;
    border: 2px solid #d4a574;
    border-radius: 8px;
    background: white;
    color: #d4a574;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  `;
  cancelBtn.addEventListener('mouseenter', () => {
    cancelBtn.style.background = '#f5f5f5';
  });
  cancelBtn.addEventListener('mouseleave', () => {
    cancelBtn.style.background = 'white';
  });
  
  cancelBtn.addEventListener('click', () => modal.remove());
  
  saveBtn.addEventListener('click', async () => {
    const text = textarea.value.trim();
    if (!text) {
      alert('업무 내용을 입력해주세요.');
      return;
    }
    
    // currentRecommendation이 없으면 (취소 후 직접 작성 모드) 직접 저장
    if (!currentRecommendation) {
      const customTask = {
        title: text,
        description: text,
        priority: 'medium',
        category: '기타',
        expected_time: '30분'
      };
      
      modal.remove();
      
      // 직접 저장 (단일 업무)
      try {
        await saveTasks(ownerId, targetDate, [customTask], addMessage);
        // 상태 초기화
        resetTaskState();
      } catch (error) {
        console.error('❌ [TaskUI] 직접 작성 업무 저장 오류:', error);
        addMessage('assistant', '❌ 업무 저장 중 오류가 발생했습니다.');
      }
      return;
    }
    
    // 추천 업무 컨테이너가 있는 경우 (기존 로직)
    // 최대 3개까지만 직접 작성 가능
    if (customTasks.length >= MAX_CUSTOM_TASKS) {
      alert(`직접 작성한 업무는 최대 ${MAX_CUSTOM_TASKS}개까지 가능합니다.`);
      return;
    }
    
    // 총 선택 개수 확인 (추천 업무 + 직접 작성)
    const totalSelected = selectedTasks.size + customTasks.length;
    if (totalSelected >= MAX_SELECTED_TASKS) {
      alert(`최대 ${MAX_SELECTED_TASKS}개의 업무만 선택할 수 있습니다.`);
      return;
    }
    
    // 직접 작성한 업무를 목록에 추가 (아직 저장하지 않음)
    const customTask = {
      title: text,
      description: text,
      priority: 'medium',
      category: '기타',
      expected_time: '30분'
    };
    
    customTasks.push(customTask);
    modal.remove();
    
    // 직접 작성한 업무 추가 완료 메시지는 표시하지 않음 (선택 완료 버튼 클릭 시 통합 재확인 메시지로 표시)
    
    // 선택 개수 업데이트
    const container = document.querySelector('.task-recommendations-container');
    if (container) {
      const totalCount = selectedTasks.size + customTasks.length;
      updateSelectionCount(container, totalCount);
      
      const saveButton = container.querySelector('.task-save-button');
      if (saveButton) {
        saveButton.disabled = totalCount === 0;
      }
    }
    
    console.log(`✅ [TaskUI] 직접 작성 업무 추가: ${customTasks.length}개 (선택된 추천 업무: ${selectedTasks.size}개, 총: ${totalCount}개)`);
  });
  
  btnWrap.appendChild(saveBtn);
  btnWrap.appendChild(cancelBtn);
  
  modalContent.appendChild(title);
  modalContent.appendChild(label);
  modalContent.appendChild(textarea);
  modalContent.appendChild(btnWrap);
  
  modal.appendChild(modalContent);
  document.body.appendChild(modal);
  
  // ESC 키로 닫기
  const handleEsc = (e) => {
    if (e.key === 'Escape') {
      modal.remove();
      document.removeEventListener('keydown', handleEsc);
    }
  };
  document.addEventListener('keydown', handleEsc);
  
  // 모달 외부 클릭 시 닫기
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.remove();
  });
  
  setTimeout(() => textarea.focus(), 80);
}

// saveCustomTask 함수는 더 이상 사용하지 않음
// 직접 작성한 업무는 customTasks 배열에 추가하고, 
// "선택 완료" 버튼을 눌렀을 때 재확인 후 함께 저장됨

/**
 * 추천 업무 상태 초기화 (Intent 고착 방지)
 */
export function resetTaskState() {
  selectedTasks.clear();
  customTasks = []; // 직접 작성한 업무도 초기화
  currentRecommendation = null;
  console.log('🔄 [TaskUI] 추천 업무 상태 초기화 (Intent 고착 방지)');
}
