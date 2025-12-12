"""Notion OAuth Client"""
from typing import Optional, Dict, Any
import httpx
import secrets
from urllib.parse import urlencode

from app.core.config import settings


class NotionOAuthClient:
    """Notion OAuth 클라이언트"""
    
    AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.notion.com/v1/oauth/token"
    
    def __init__(self):
        self.client_id = settings.NOTION_CLIENT_ID
        self.client_secret = settings.NOTION_CLIENT_SECRET
        self.redirect_uri = settings.NOTION_REDIRECT_URI
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Notion OAuth 로그인 URL 생성
        
        Returns:
            Notion 로그인 페이지 URL
        """
        # 디버깅: client_id 확인
        print(f"[DEBUG] Notion Client ID: {self.client_id[:10]}..." if self.client_id else "[DEBUG] Notion Client ID: NOT SET")
        print(f"[DEBUG] Redirect URI: {self.redirect_uri}")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Notion OAuth credentials not configured. Please set NOTION_CLIENT_ID and NOTION_CLIENT_SECRET in .env")
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "owner": "user",  # 사용자 개인 워크스페이스 연동
            "state": state or secrets.token_urlsafe(16)
        }
        
        url = f"{self.AUTHORIZE_URL}?{urlencode(params)}"
        print(f"[DEBUG] Generated OAuth URL: {url}")
        return url
    
    async def get_access_token(self, code: str) -> Dict[str, Any]:
        """
        Authorization Code로 Access Token 받기
        
        Args:
            code: Notion에서 받은 Authorization Code
        
        Returns:
            토큰 정보 dict (access_token, workspace_id, workspace_name 등 포함)
        """
        # Notion은 Basic Auth 사용
        import base64
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                headers={
                    "Authorization": f"Basic {encoded_credentials}",
                    "Content-Type": "application/json"
                },
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Notion 응답 구조:
            # {
            #   "access_token": "...",
            #   "token_type": "bearer",
            #   "bot_id": "...",
            #   "workspace_id": "...",
            #   "workspace_name": "...",
            #   "workspace_icon": "...",
            #   "owner": {...}
            # }
            
            return data


# 싱글톤 인스턴스
notion_oauth = NotionOAuthClient()

