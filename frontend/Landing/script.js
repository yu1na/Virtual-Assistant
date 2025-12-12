/**
 * 쿠키에서 값 가져오기
 */
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return decodeURIComponent(parts.pop().split(';').shift());
    }
    return null;
}

/**
 * 쿠키 삭제
 */
function deleteCookie(name) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}

/**
 * 로그인 여부 확인
 */
function isLoggedIn() {
    const loggedIn = getCookie('logged_in');
    return loggedIn === 'true';
}

/**
 * 사용자 정보 가져오기
 */
function getUserInfo() {
    const userEncoded = getCookie('user');
    if (userEncoded) {
        try {
            const userJson = decodeURIComponent(userEncoded);
            return JSON.parse(userJson);
        } catch (e) {
            console.error('사용자 정보 파싱 실패:', e);
            return null;
        }
    }
    return null;
}

/**
 * [시작하기] 버튼 클릭
 */
function handleStartClick() {
    console.log('🚀 시작하기 버튼 클릭');
    
    // 로그인 체크
    if (!isLoggedIn()) {
        alert('로그인이 필요합니다.');
        console.log('❌ 로그인 필요 - /login으로 이동');
        window.location.href = '/login';
        return;
    }
    
    console.log('✅ 로그인 확인됨 - 메인 앱 시작');
    
    // Electron인지 확인
    if (typeof window.require !== 'undefined') {
        try {
            // Electron에서는 IPC로 캐릭터 창 열기
            const { ipcRenderer } = window.require('electron');
            console.log('IPC 메시지 전송: va:start-character');
            ipcRenderer.send('va:start-character');
        } catch (err) {
            console.error('IPC 전송 실패:', err);
            alert('캐릭터 창을 열 수 없습니다.');
        }
    } else {
        // 브라우저에서는 메인 페이지로 이동
        console.log('브라우저 모드 - /main으로 이동');
        window.location.href = '/main';
    }
}

/**
 * 로그인 트리거 클릭
 */
function handleLoginTriggerClick() {
    if (isLoggedIn()) {
        // 로그인 상태: 드롭다운 토글
        const dropdownMenu = document.getElementById('dropdownMenu');
        if (dropdownMenu) {
            dropdownMenu.classList.toggle('show');
        }
    } else {
        // 로그아웃 상태: 로그인 페이지로 이동
        console.log('🔐 로그인 클릭 - /login으로 이동');
        window.location.href = '/login';
    }
}

/**
 * "다른 간편 로그인" 클릭
 */
function handleChangeLoginClick() {
    console.log('🔄 다른 간편 로그인 클릭 - /login으로 이동');
    
    // relogin 파라미터 추가 (자동 리다이렉트 방지)
    const loginUrl = '/login?relogin=true';
    
    // Electron 환경 체크
    if (typeof window.require !== 'undefined') {
        try {
            // Electron에서는 현재 윈도우에서 페이지 로드
            const { ipcRenderer } = window.require('electron');
            ipcRenderer.send('va:navigate', loginUrl);
        } catch (err) {
            console.error('IPC 전송 실패:', err);
            // 실패 시 일반 페이지 이동
            window.location.href = loginUrl;
        }
    } else {
        // 브라우저에서는 일반 페이지 이동
        window.location.href = loginUrl;
    }
}

/**
 * "Slack 연동하기" 클릭
 */
async function handleSlackConnectClick() {
    console.log('💬 Slack 연동 클릭');
    
    // 로그인 체크
    if (!isLoggedIn()) {
        alert('먼저 로그인이 필요합니다.');
        window.location.href = '/login';
        return;
    }
    
    try {
        // Slack OAuth URL 요청
        const response = await fetch('http://localhost:8000/api/v1/auth/slack/login');
        const data = await response.json();
        
        if (data.authorization_url) {
            console.log('🔗 Slack OAuth URL:', data.authorization_url);
            // Slack OAuth 페이지로 이동
            window.location.href = data.authorization_url;
        } else {
            alert('Slack 연동 URL을 가져올 수 없습니다.');
        }
    } catch (error) {
        console.error('❌ Slack 연동 오류:', error);
        alert('Slack 연동 중 오류가 발생했습니다.');
    }
}

/**
 * "Notion 연동하기" 클릭
 */
async function handleNotionConnectClick() {
    console.log('📚 Notion 연동 클릭');
    
    // 로그인 체크
    if (!isLoggedIn()) {
        alert('먼저 로그인이 필요합니다.');
        window.location.href = '/login';
        return;
    }
    
    try {
        // Notion OAuth URL 요청
        const response = await fetch('http://localhost:8000/api/v1/auth/notion/login');
        const data = await response.json();
        
        if (data.authorization_url) {
            console.log('🔗 Notion OAuth URL:', data.authorization_url);
            
            // Electron 환경 체크
            if (typeof window.require !== 'undefined') {
                try {
                    // Electron에서는 새 창으로 OAuth 처리
                    const { ipcRenderer } = window.require('electron');
                    ipcRenderer.send('open-notion-oauth', data.authorization_url);
                    console.log('✅ Notion OAuth 창 열기');
                } catch (err) {
                    console.error('OAuth 창 열기 실패:', err);
                    // 실패 시 일반 방식으로 시도
                    window.location.href = data.authorization_url;
                }
            } else {
                // 브라우저에서는 일반 방식으로 이동
                window.location.href = data.authorization_url;
            }
        } else {
            alert('Notion 연동 URL을 가져올 수 없습니다.');
        }
    } catch (error) {
        console.error('❌ Notion 연동 오류:', error);
        alert('Notion 연동 중 오류가 발생했습니다.');
    }
}

/**
 * "로그아웃" 클릭
 */
function handleLogoutClick() {
    if (confirm('정말 로그아웃하시겠습니까?')) {
        console.log('🚪 로그아웃 처리');
        
        // 쿠키 삭제
        deleteCookie('access_token');
        deleteCookie('refresh_token');
        deleteCookie('user');
        deleteCookie('logged_in');
        deleteCookie('slack_access_token');
        deleteCookie('slack_team_name');
        deleteCookie('notion_workspace');
        
        // 페이지 새로고침
        console.log('🔄 페이지 새로고침');
        window.location.reload();
    }
}

/**
 * 드롭다운 외부 클릭 시 닫기
 */
function handleOutsideClick(event) {
    const dropdown = document.getElementById('dropdownMenu');
    const trigger = document.getElementById('loginTrigger');
    
    if (dropdown && trigger && 
        !dropdown.contains(event.target) && 
        !trigger.contains(event.target)) {
        dropdown.classList.remove('show');
    }
}

/**
 * 우측 상단 로그인 UI 업데이트
 */
function updateLoginUI() {
    const loggedIn = isLoggedIn();
    const loginTrigger = document.getElementById('loginTrigger');
    const dropdownMenu = document.getElementById('dropdownMenu');
    
    if (loggedIn) {
        // 로그인 상태
        const userInfo = getUserInfo();
        const userName = userInfo ? (userInfo.name || userInfo.email.split('@')[0]) : '사용자';
        
        if (loginTrigger) {
            loginTrigger.textContent = `${userName} 님`;
        }
        
        console.log(`✅ 로그인 상태: ${userName}`);
    } else {
        // 로그아웃 상태
        if (loginTrigger) {
            loginTrigger.textContent = '로그인';
        }
        
        // 드롭다운 숨김
        if (dropdownMenu) {
            dropdownMenu.classList.remove('show');
        }
        
        console.log('❌ 로그인 안 됨');
    }
}

/**
 * 페이지 로드 시 실행
 */
window.addEventListener('DOMContentLoaded', () => {
    console.log('📄 Landing 페이지 로드');
    
    // URL 파라미터 체크 (Notion 연동 성공 메시지)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('notion_connected') === 'true') {
        const workspace = urlParams.get('workspace') || 'Notion';
        alert('✅ ' + workspace + ' 연동이 완료되었습니다!');
        // URL 파라미터 제거
        window.history.replaceState({}, document.title, '/landing');
    }
    
    // 에러 메시지 표시
    if (urlParams.get('error')) {
        const errorMsg = urlParams.get('message') || '연동 중 오류가 발생했습니다.';
        alert(`❌ ${errorMsg}`);
        window.history.replaceState({}, document.title, '/landing');
    }
    
    // 우측 상단 로그인 UI 업데이트
    updateLoginUI();
    
    // 버튼 이벤트 연결
    const startBtn = document.getElementById('startBtn');
    const loginTrigger = document.getElementById('loginTrigger');
    const changeLoginBtn = document.getElementById('changeLoginBtn');
    const slackConnectBtn = document.getElementById('slackConnectBtn');
    const notionConnectBtn = document.getElementById('notionConnectBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    
    if (startBtn) {
        startBtn.addEventListener('click', handleStartClick);
    }
    
    if (loginTrigger) {
        loginTrigger.addEventListener('click', handleLoginTriggerClick);
    }
    
    if (changeLoginBtn) {
        changeLoginBtn.addEventListener('click', handleChangeLoginClick);
    }
    
    if (slackConnectBtn) {
        slackConnectBtn.addEventListener('click', handleSlackConnectClick);
    }
    
    if (notionConnectBtn) {
        notionConnectBtn.addEventListener('click', handleNotionConnectClick);
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogoutClick);
    }
    
    // 드롭다운 외부 클릭 감지
    document.addEventListener('click', handleOutsideClick);
});

