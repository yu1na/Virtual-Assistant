from typing import Optional
from authlib.integrations.httpx_client import AsyncOAuth2Client
import httpx
import secrets

from app.core.config import settings
from app.domain.auth.schemas import OAuthUserInfo


class GoogleOAuthClient:
    """Google OAuth 클라이언트"""
    
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    # 필요한 모든 권한을 여기에 하드코딩
    SCOPES = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/drive"
    ]

    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Google OAuth 로그인 URL 생성
        
        Returns:
            Google 로그인 페이지 URL
        """
        # 하드코딩된 스코프 사용
        scope_str = " ".join(self.SCOPES)
        
        # 1. AsyncOAuth2Client 인스턴스 생성
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=scope_str
        )
        
        # 2. URL 생성
        # prompt='consent'로 권한 재동의 강제
        url, _ = client.create_authorization_url(
            self.AUTHORIZE_URL,
            state=state or secrets.token_urlsafe(16),
            access_type="offline",  
            prompt="consent",
            include_granted_scopes="true" 
        )
        
        return url
    
    async def get_access_token(self, code: str) -> dict:
        """
        Authorization Code로 Access Token 받기
        
        Args:
            code: Google에서 받은 Authorization Code
        
        Returns:
            토큰 정보 dict
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Access Token으로 사용자 정보 가져오기
        
        Args:
            access_token: Google Access Token
        
        Returns:
            OAuthUserInfo 객체
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return OAuthUserInfo(
                email=data["email"],
                name=data.get("name"),
                profile_image=data.get("picture"),
                oauth_id=data["id"],
                oauth_provider="google"
            )


# 싱글톤 인스턴스
google_oauth = GoogleOAuthClient()