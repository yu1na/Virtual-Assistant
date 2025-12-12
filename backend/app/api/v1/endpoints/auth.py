from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode
import time

from app.infrastructure.database import get_db
from app.domain.auth.service import AuthService
from app.domain.auth.schemas import OAuthCallbackResponse, RefreshTokenRequest, Token
from app.infrastructure.oauth import google_oauth, kakao_oauth, naver_oauth, notion_oauth
from app.core.config import settings

# Tools OAuth 토큰 저장
import sys
from pathlib import Path

# 동적 경로 탐색: tools/token_manager.py가 있는 상위 디렉토리를 찾음
current_path = Path(__file__).resolve()
project_root = None

while current_path.parent != current_path:  # 루트 디렉토리 도달 시 종료
    parent = current_path.parent
    
    # tools/token_manager.py 파일이 존재하는지 확인
    token_manager_path = parent / "tools" / "token_manager.py"
    if token_manager_path.exists():
        project_root = parent
        break
    
    current_path = parent

# 경로 설정 및 임포트
if project_root:
    print(f"✅ 프로젝트 루트 발견: {project_root}")
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
else:
    # Fallback: 6단계 상위 (Virtual-Assistant/Virtual-Assistant)
    # auth.py -> endpoints -> v1 -> api -> app -> backend -> Virtual-Assistant
    fallback_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    print(f"⚠️ 동적 탐색 실패. 기본 경로 사용: {fallback_root}")
    if str(fallback_root) not in sys.path:
        sys.path.insert(0, str(fallback_root))

try:
    from tools.token_manager import save_token
    TOOLS_AVAILABLE = True
    print(f"✅ tools.token_manager 임포트 성공")
except ImportError as e:
    TOOLS_AVAILABLE = False
    print(f"❌ tools.token_manager 임포트 실패: {e}")
    # 디버깅을 위해 sys.path 출력
    print(f"   sys.path: {sys.path}")

router = APIRouter()


# ========================================
# Google OAuth
# ========================================

# 기존 google_login 함수를 이걸로 통째로 교체하세요!

@router.get("/google/login")
async def google_login():
    """
    Google OAuth 로그인 URL 반환
    """
    authorization_url = google_oauth.get_authorization_url()
    return {"authorization_url": authorization_url}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Google Authorization Code"),
    db: Session = Depends(get_db)
):
    """
    Google OAuth 콜백
    
    Google 로그인 후 리다이렉트되는 엔드포인트
    로그인 성공 시 토큰을 쿠키에 저장하고 /start로 리다이렉트
    """
    print(f"\n{'='*60}")
    print(f"🔵 Google OAuth 콜백 시작")
    print(f"{'='*60}")
    print(f"   Authorization Code 받음: {code[:20]}...")
    
    try:
        # Access Token 받기
        print(f"   1️⃣ Google에 Access Token 요청 중...")
        token_data = await google_oauth.get_access_token(code)
        print(f"   ✅ Access Token 받음")
        access_token = token_data["access_token"]
        
        # 사용자 정보 가져오기
        print(f"   2️⃣ Google에 사용자 정보 요청 중...")
        user_info = await google_oauth.get_user_info(access_token)
        print(f"   ✅ 사용자 정보 받음: {user_info.email}")
        
        # 로그인 처리 (사용자 조회/생성 + JWT 발급)
        print(f"   3️⃣ 데이터베이스에서 사용자 조회/생성 중...")
        auth_service = AuthService(db)
        result = auth_service.oauth_login(user_info)
        print(f"   ✅ 사용자 처리 완료: {result.user.email}")
        
        # OAuth 토큰 저장 (Tools 사용을 위해)
        if TOOLS_AVAILABLE:
            try:
                await save_token(
                    user_id=str(result.user.id),
                    service="google",
                    token_data={
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token"),
                        "token_type": token_data.get("token_type", "Bearer"),
                        "expires_at": int(time.time()) + token_data.get("expires_in", 3600)
                    }
                )
                print(f"✅ Google OAuth 토큰 저장 완료 (user_id: {result.user.id})")
            except Exception as e:
                print(f"⚠️ OAuth 토큰 저장 실패: {e}")
        
        # 쿠키에 토큰 저장하고 /landing으로 리다이렉트
        print(f"\n{'='*60}")
        print(f"🍪 Google OAuth 콜백 - 쿠키 설정 시작")
        print(f"{'='*60}")
        print(f"   - DEBUG 모드: {settings.DEBUG}")
        
        # 개발 환경(localhost)에서는 Secure=False, SameSite=Lax로 설정해야 쿠키가 전송됨
        secure_cookie = not settings.DEBUG
        samesite_policy = "Lax" if settings.DEBUG else "None"
        
        print(f"   - Secure 설정: {secure_cookie}")
        print(f"   - SameSite 설정: {samesite_policy}")
        print(f"   - 사용자: {result.user.email} (ID: {result.user.id})")
        print(f"   - Access Token 길이: {len(result.access_token)}")
        print(f"   - Refresh Token 길이: {len(result.refresh_token)}")
        
        response = RedirectResponse(url="/landing", status_code=302)
        
        # Access Token 쿠키 (HttpOnly)
        response.set_cookie(
            key="access_token",
            value=result.access_token,
            httponly=True,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            domain=None
        )
        print(f"   ✅ access_token 쿠키 설정 완료")
        
        # Refresh Token 쿠키 (HttpOnly)
        response.set_cookie(
            key="refresh_token",
            value=result.refresh_token,
            httponly=True,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
            domain=None
        )
        print(f"   ✅ refresh_token 쿠키 설정 완료")
        
        # 사용자 정보는 일반 쿠키로 (프론트엔드에서 읽을 수 있도록)
        import json
        from urllib.parse import quote
        user_data = {
            "id": result.user.id,  # ID 추가
            "email": result.user.email,
            "name": result.user.name or ""
        }
        # 한글 등 유니코드 문자를 위해 URL 인코딩
        user_json = json.dumps(user_data, ensure_ascii=False)
        user_encoded = quote(user_json)
        
        response.set_cookie(
            key="user",
            value=user_encoded,
            httponly=False,  # JavaScript에서 읽을 수 있도록
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
            domain=None
        )
        print(f"   ✅ user 쿠키 설정 완료 (URL 인코딩, ID 포함)")
        
        # 로그인 상태 확인용 쿠키 (HttpOnly=false)
        response.set_cookie(
            key="logged_in",
            value="true",
            httponly=False,  # JavaScript에서 읽을 수 있도록
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            domain=None
        )
        print(f"   ✅ logged_in 쿠키 설정 완료")
        print(f"\n🔄 /landing으로 리다이렉트")
        print(f"   Set-Cookie 헤더:")
        for key, value in response.headers.items():
            if key.lower() == 'set-cookie':
                print(f"      {key}: {value[:100]}...")
        print(f"{'='*60}\n")
        
        return response
    
    except Exception as e:
        # 에러 발생 시 로그인 페이지로 리다이렉트 (에러 메시지 포함)
        print(f"\n{'='*60}")
        print(f"❌ Google OAuth 콜백 에러 발생!")
        print(f"{'='*60}")
        print(f"에러 타입: {type(e).__name__}")
        print(f"에러 메시지: {str(e)}")
        import traceback
        print(f"상세 스택:")
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        error_params = {'error': str(e)}
        redirect_url = f"/login?{urlencode(error_params)}"
        return RedirectResponse(url=redirect_url)


# ========================================
# Kakao OAuth
# ========================================

@router.get("/kakao/login")
async def kakao_login():
    """Kakao OAuth 로그인 URL 반환"""
    authorization_url = kakao_oauth.get_authorization_url()
    return {"authorization_url": authorization_url}


@router.get("/kakao/callback")
async def kakao_callback(
    code: str = Query(..., description="Kakao Authorization Code"),
    db: Session = Depends(get_db)
):
    """Kakao OAuth 콜백"""
    try:
        # Access Token 받기
        token_data = await kakao_oauth.get_access_token(code)
        access_token = token_data["access_token"]
        
        # 사용자 정보 가져오기
        user_info = await kakao_oauth.get_user_info(access_token)
        
        # 로그인 처리
        auth_service = AuthService(db)
        result = auth_service.oauth_login(user_info)
        
        # 쿠키 설정 준비
        secure_cookie = not settings.DEBUG
        samesite_policy = "Lax" if settings.DEBUG else "None"
        
        # 쿠키에 토큰 저장하고 /start로 리다이렉트
        response = RedirectResponse(url="/start", status_code=302)
        
        # Access Token 쿠키
        response.set_cookie(
            key="access_token",
            value=result.access_token,
            httponly=True,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            domain=None
        )
        
        # Refresh Token 쿠키
        response.set_cookie(
            key="refresh_token",
            value=result.refresh_token,
            httponly=True,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
            domain=None
        )
        
        # 사용자 정보 쿠키
        import json
        from urllib.parse import quote
        user_data = {
            "id": result.user.id,
            "email": result.user.email,
            "name": result.user.name or ""
        }
        # 한글 등 유니코드 문자를 위해 URL 인코딩
        user_json = json.dumps(user_data, ensure_ascii=False)
        user_encoded = quote(user_json)
        
        response.set_cookie(
            key="user",
            value=user_encoded,
            httponly=False,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
            domain=None
        )
        
        # 로그인 상태 확인용 쿠키
        response.set_cookie(
            key="logged_in",
            value="true",
            httponly=False,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            domain=None
        )
        
        print(f"✅ Kakao 로그인 성공 - 쿠키 설정 완료: {result.user.email}")
        
        return response
    
    except Exception as e:
        print(f"\n❌ Kakao OAuth 콜백 에러: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        
        error_params = {'error': str(e)}
        redirect_url = f"/login?{urlencode(error_params)}"
        return RedirectResponse(url=redirect_url)


# ========================================
# Naver OAuth
# ========================================

@router.get("/naver/login")
async def naver_login():
    """Naver OAuth 로그인 URL 반환"""
    authorization_url = naver_oauth.get_authorization_url()
    return {"authorization_url": authorization_url}


@router.get("/naver/callback")
async def naver_callback(
    code: str = Query(..., description="Naver Authorization Code"),
    state: str = Query(..., description="CSRF State"),
    db: Session = Depends(get_db)
):
    """Naver OAuth 콜백"""
    try:
        # Access Token 받기
        token_data = await naver_oauth.get_access_token(code, state)
        access_token = token_data["access_token"]
        
        # 사용자 정보 가져오기
        user_info = await naver_oauth.get_user_info(access_token)
        
        # 로그인 처리
        auth_service = AuthService(db)
        result = auth_service.oauth_login(user_info)
        
        # 쿠키 설정 준비
        secure_cookie = not settings.DEBUG
        samesite_policy = "Lax" if settings.DEBUG else "None"
        
        # 쿠키에 토큰 저장하고 /start로 리다이렉트
        response = RedirectResponse(url="/start", status_code=302)
        
        # Access Token 쿠키
        response.set_cookie(
            key="access_token",
            value=result.access_token,
            httponly=True,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            domain=None
        )
        
        # Refresh Token 쿠키
        response.set_cookie(
            key="refresh_token",
            value=result.refresh_token,
            httponly=True,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
            domain=None
        )
        
        # 사용자 정보 쿠키
        import json
        from urllib.parse import quote
        user_data = {
            "id": result.user.id,
            "email": result.user.email,
            "name": result.user.name or ""
        }
        # 한글 등 유니코드 문자를 위해 URL 인코딩
        user_json = json.dumps(user_data, ensure_ascii=False)
        user_encoded = quote(user_json)
        
        response.set_cookie(
            key="user",
            value=user_encoded,
            httponly=False,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
            domain=None
        )
        
        # 로그인 상태 확인용 쿠키
        response.set_cookie(
            key="logged_in",
            value="true",
            httponly=False,
            secure=secure_cookie,
            samesite=samesite_policy,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            domain=None
        )
        
        print(f"✅ Naver 로그인 성공 - 쿠키 설정 완료: {result.user.email}")
        
        return response
    
    except Exception as e:
        print(f"\n❌ Naver OAuth 콜백 에러: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        
        error_params = {'error': str(e)}
        redirect_url = f"/login?{urlencode(error_params)}"
        return RedirectResponse(url=redirect_url)


# ========================================
# Slack OAuth (사용자 개인 연동)
# ========================================

@router.get("/slack/login")
async def slack_login():
    """
    Slack OAuth 로그인 URL 반환
    
    프론트엔드에서 이 URL로 리다이렉트
    """
    # Slack OAuth URL 생성
    params = {
        "client_id": settings.SLACK_CLIENT_ID,
        "scope": "chat:write,channels:read,users:read,im:write",  # 필요한 권한
        "redirect_uri": settings.SLACK_REDIRECT_URI,
        "response_type": "code"
    }
    authorization_url = f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
    return {"authorization_url": authorization_url}


@router.get("/slack/callback")
async def slack_callback(
    code: str = Query(..., description="Slack Authorization Code"),
    db: Session = Depends(get_db)
):
    """
    Slack OAuth 콜백
    
    Slack에서 인증 후 이 엔드포인트로 리다이렉트됨
    """
    try:
        print(f"\n🔵 Slack OAuth 콜백 시작")
        print(f"📦 Code: {code[:20]}...")
        
        # 1. Slack에서 Access Token 교환
        import httpx
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": settings.SLACK_CLIENT_ID,
                    "client_secret": settings.SLACK_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.SLACK_REDIRECT_URI
                }
            )
            
            token_data = token_response.json()
            
            if not token_data.get("ok"):
                error_msg = token_data.get("error", "Unknown error")
                print(f"❌ Slack 토큰 교환 실패: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Slack OAuth 실패: {error_msg}"
                )
            
            access_token = token_data.get("access_token")
            team_id = token_data.get("team", {}).get("id")
            team_name = token_data.get("team", {}).get("name")
            
            print(f"✅ Slack 토큰 획득 성공")
            print(f"📋 Team: {team_name} ({team_id})")
        
        # 2. 현재 로그인된 사용자 확인 (쿠키에서)
        # 실제로는 Request에서 쿠키를 읽어야 하지만, 
        # 여기서는 간단히 리다이렉트로 처리
        # 프론트엔드에서 user_id를 전달하거나, 쿠키에서 JWT를 파싱해야 함
        
        # 임시: 쿠키에 Slack 토큰 저장 (나중에 user_id와 연결)
        response = RedirectResponse(url="/landing?slack_connected=true", status_code=302)
        
        # Slack 토큰을 쿠키에 임시 저장
        response.set_cookie(
            key="slack_access_token",
            value=access_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=60 * 60 * 24 * 365,  # 1년 (Slack 토큰은 만료되지 않음)
            path="/",
            domain=None
        )
        
        response.set_cookie(
            key="slack_team_name",
            value=team_name,
            httponly=False,
            secure=False,
            samesite="Lax",
            max_age=60 * 60 * 24 * 365,
            path="/",
            domain=None
        )
        
        print(f"✅ Slack 연동 완료 - 쿠키 설정 완료: {team_name}")
        
        return response
    
    except Exception as e:
        print(f"\n❌ Slack OAuth 콜백 에러: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        
        error_params = {'error': str(e), 'slack_error': 'true'}
        redirect_url = f"/landing?{urlencode(error_params)}"
        return RedirectResponse(url=redirect_url)


# ========================================
# Notion OAuth (사용자 개인 연동)
# ========================================

@router.get("/notion/login")
async def notion_login():
    """
    Notion OAuth 로그인 URL 반환
    
    프론트엔드에서 이 URL로 리다이렉트하여 Notion 연동 시작
    """
    print("\n🔵 Notion OAuth 로그인 요청")
    authorization_url = notion_oauth.get_authorization_url()
    print(f"✅ Notion OAuth URL 생성: {authorization_url[:50]}...")
    return {"authorization_url": authorization_url}


@router.get("/notion/callback")
async def notion_callback(
    request: Request,
    code: str = Query(..., description="Notion Authorization Code"),
    state: str = Query(None, description="State parameter")
):
    """
    Notion OAuth 콜백
    
    Notion 연동 후 리다이렉트되는 엔드포인트
    토큰을 token_manager에 저장하고 /landing으로 리다이렉션
    
    ⚠️ 중요: 기존 로그인 세션 유지 (쿠키에서 user 정보 읽기)
    """
    print(f"\n{'='*60}")
    print(f"🟣 Notion OAuth 콜백 시작")
    print(f"{'='*60}")
    print(f"   Authorization Code 받음: {code[:20]}...")
    
    try:
        # 1. Access Token 받기
        print(f"   1️⃣ Notion에 Access Token 요청 중...")
        token_data = await notion_oauth.get_access_token(code)
        print(f"   ✅ Access Token 받음")
        
        access_token = token_data.get("access_token")
        workspace_id = token_data.get("workspace_id")
        workspace_name = token_data.get("workspace_name", "Unknown Workspace")
        bot_id = token_data.get("bot_id")
        
        print(f"   📦 Workspace: {workspace_name} (ID: {workspace_id})")
        
        # 2. 쿠키에서 현재 로그인한 사용자 정보 가져오기 (중요!)
        print(f"   2️⃣ 현재 로그인 사용자 확인 중...")
        from urllib.parse import unquote
        import json
        
        user_cookie = request.cookies.get("user")
        if not user_cookie:
            print(f"   ❌ 로그인 세션이 없습니다 - user 쿠키 없음")
            error_params = {'error': 'not_logged_in', 'message': '먼저 로그인이 필요합니다'}
            redirect_url = f"/landing?{urlencode(error_params)}"
            return RedirectResponse(url=redirect_url, status_code=302)
        
        try:
            user_json = unquote(user_cookie)
            user_data = json.loads(user_json)
            user_id = str(user_data.get("id"))
            user_email = user_data.get("email")
            print(f"   ✅ 로그인 사용자 확인: {user_email} (ID: {user_id})")
        except Exception as parse_error:
            print(f"   ❌ user 쿠키 파싱 실패: {parse_error}")
            error_params = {'error': 'invalid_session', 'message': '세션 정보가 올바르지 않습니다'}
            redirect_url = f"/landing?{urlencode(error_params)}"
            return RedirectResponse(url=redirect_url, status_code=302)
        
        # 3. token_manager에 토큰 저장
        print(f"   3️⃣ Notion 토큰 저장 중...")
        
        try:
            # token_manager에 저장할 데이터
            notion_token_data = {
                "access_token": access_token,
                "workspace_id": workspace_id,
                "workspace_name": workspace_name,
                "bot_id": bot_id,
                "token_type": token_data.get("token_type", "bearer")
            }
            
            # token_manager를 사용하여 저장
            await save_token(user_id, "notion", notion_token_data)
            print(f"   ✅ Notion 토큰 저장 완료: {workspace_name}")
        except Exception as save_error:
            print(f"   ❌ 토큰 저장 실패: {save_error}")
            import traceback
            traceback.print_exc()
            # 저장 실패해도 계속 진행 (사용자에게 알림)
            error_params = {'error': 'token_save_failed', 'message': '토큰 저장에 실패했습니다'}
            redirect_url = f"/landing?{urlencode(error_params)}"
            response = RedirectResponse(url=redirect_url, status_code=302)
            return response
        
        # 4. /landing으로 리다이렉션 (쿠키 유지)
        print(f"   4️⃣ /landing으로 리다이렉션")
        
        from urllib.parse import quote
        import base64
        
        workspace_encoded = quote(workspace_name)
        redirect_url = f"/landing?notion_connected=true&workspace={workspace_encoded}"
        print(f"✅ Notion OAuth 콜백 완료 - 리다이렉션: {redirect_url}")
        
        # Response 객체 생성 (status_code=302 명시)
        response = RedirectResponse(url=redirect_url, status_code=302)
        
        # Notion workspace 정보를 쿠키에 저장 (한글 인코딩 문제 해결: base64 사용)
        workspace_name_encoded = base64.b64encode(workspace_name.encode('utf-8')).decode('ascii')
        response.set_cookie(
            key="notion_workspace",
            value=workspace_name_encoded,
            httponly=False,
            secure=False,
            samesite="Lax",
            max_age=60 * 60 * 24 * 365,
            path="/",
            domain=None
        )
        
        return response
    
    except Exception as e:
        print(f"\n❌ Notion OAuth 콜백 에러: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        
        error_params = {'error': 'notion_auth_failed', 'message': str(e)}
        redirect_url = f"/landing?{urlencode(error_params)}"
        return RedirectResponse(url=redirect_url, status_code=302)


# ========================================
# Token Refresh
# ========================================

@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh Token으로 새 Access Token 발급
    """
    auth_service = AuthService(db)
    return auth_service.refresh_access_token(request.refresh_token)
