"""
Slack API 서비스
사용자별 Slack 토큰을 사용하여 메시지 전송, 채널 조회 등
"""

import httpx
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.domain.user.token_models import UserToken


class SlackService:
    """Slack API 호출 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_user_token(self, user_id: int) -> Optional[str]:
        """사용자의 Slack Access Token 조회"""
        token_record = self.db.query(UserToken).filter(
            UserToken.user_id == user_id,
            UserToken.service == "slack"
        ).first()
        
        if not token_record:
            return None
        
        return token_record.access_token
    
    async def save_user_token(
        self, 
        user_id: int, 
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[int] = None
    ) -> bool:
        """사용자의 Slack Access Token 저장"""
        try:
            existing_token = self.db.query(UserToken).filter(
                UserToken.user_id == user_id,
                UserToken.service == "slack"
            ).first()
            
            if existing_token:
                # 업데이트
                existing_token.access_token = access_token
                existing_token.refresh_token = refresh_token
                existing_token.expires_at = expires_at
            else:
                # 새로 생성
                new_token = UserToken(
                    user_id=user_id,
                    service="slack",
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_type="Bearer",
                    expires_at=expires_at
                )
                self.db.add(new_token)
            
            self.db.commit()
            return True
        
        except Exception as e:
            self.db.rollback()
            print(f"Slack 토큰 저장 실패: {str(e)}")
            return False
    
    async def send_message(
        self, 
        user_id: int, 
        channel: str, 
        text: str,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Slack 채널에 메시지 전송"""
        access_token = await self.get_user_token(user_id)
        
        if not access_token:
            return {
                "success": False,
                "error": "Slack이 연동되지 않았습니다. 먼저 Slack 연동을 완료해주세요."
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "channel": channel,
                        "text": text,
                        "thread_ts": thread_ts
                    }
                )
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "data": {
                            "channel": data.get("channel"),
                            "ts": data.get("ts"),
                            "message": data.get("message", {})
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"메시지 전송 실패: {data.get('error', 'Unknown error')}"
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"메시지 전송 중 오류: {str(e)}"
            }
    
    async def send_dm(
        self, 
        user_id: int, 
        slack_user_id: str, 
        text: str
    ) -> Dict[str, Any]:
        """Slack DM (Direct Message) 전송"""
        access_token = await self.get_user_token(user_id)
        
        if not access_token:
            return {
                "success": False,
                "error": "Slack이 연동되지 않았습니다."
            }
        
        try:
            async with httpx.AsyncClient() as client:
                # 1. DM 채널 열기
                open_response = await client.post(
                    "https://slack.com/api/conversations.open",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"users": slack_user_id}
                )
                
                open_data = open_response.json()
                
                if not open_data.get("ok"):
                    return {
                        "success": False,
                        "error": f"DM 채널 열기 실패: {open_data.get('error', 'Unknown error')}"
                    }
                
                channel_id = open_data["channel"]["id"]
                
                # 2. 메시지 전송
                return await self.send_message(user_id, channel_id, text)
        
        except Exception as e:
            return {
                "success": False,
                "error": f"DM 전송 중 오류: {str(e)}"
            }
    
    async def list_channels(
        self, 
        user_id: int,
        types: str = "public_channel,private_channel",
        limit: int = 100
    ) -> Dict[str, Any]:
        """Slack 채널 목록 조회"""
        access_token = await self.get_user_token(user_id)
        
        if not access_token:
            return {
                "success": False,
                "error": "Slack이 연동되지 않았습니다."
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/conversations.list",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"types": types, "limit": limit}
                )
                
                data = response.json()
                
                if data.get("ok"):
                    channels = data.get("channels", [])
                    return {
                        "success": True,
                        "data": {
                            "count": len(channels),
                            "channels": [
                                {
                                    "id": ch.get("id"),
                                    "name": ch.get("name"),
                                    "is_private": ch.get("is_private", False),
                                    "is_member": ch.get("is_member", False),
                                    "num_members": ch.get("num_members", 0)
                                }
                                for ch in channels
                            ]
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"채널 목록 조회 실패: {data.get('error', 'Unknown error')}"
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"채널 목록 조회 중 오류: {str(e)}"
            }
    
    async def get_user_info(
        self, 
        user_id: int, 
        slack_user_id: str
    ) -> Dict[str, Any]:
        """Slack 사용자 정보 조회"""
        access_token = await self.get_user_token(user_id)
        
        if not access_token:
            return {
                "success": False,
                "error": "Slack이 연동되지 않았습니다."
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/users.info",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"user": slack_user_id}
                )
                
                data = response.json()
                
                if data.get("ok"):
                    user = data.get("user", {})
                    profile = user.get("profile", {})
                    return {
                        "success": True,
                        "data": {
                            "id": user.get("id"),
                            "name": user.get("name"),
                            "real_name": user.get("real_name"),
                            "display_name": profile.get("display_name"),
                            "email": profile.get("email"),
                            "is_bot": user.get("is_bot", False)
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"사용자 정보 조회 실패: {data.get('error', 'Unknown error')}"
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"사용자 정보 조회 중 오류: {str(e)}"
            }
    
    async def check_connection(self, user_id: int) -> Dict[str, Any]:
        """Slack 연동 상태 확인"""
        access_token = await self.get_user_token(user_id)
        
        if not access_token:
            return {
                "connected": False,
                "message": "Slack이 연동되지 않았습니다."
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "connected": True,
                        "data": {
                            "team": data.get("team"),
                            "team_id": data.get("team_id"),
                            "user": data.get("user"),
                            "user_id": data.get("user_id")
                        }
                    }
                else:
                    return {
                        "connected": False,
                        "message": "Slack 토큰이 유효하지 않습니다."
                    }
        
        except Exception as e:
            return {
                "connected": False,
                "message": f"연결 확인 중 오류: {str(e)}"
            }

