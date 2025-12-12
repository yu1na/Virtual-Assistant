"""Gmail API Tool (공식 SDK 사용)"""
import os
import base64
from typing import Optional, Dict, Any, List, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from .token_manager import load_token

from html.parser import HTMLParser
import re


class _HTMLToMarkdown(HTMLParser):
    """
    간단한 HTML -> Markdown 변환기 (외부 의존성 없이 동작)
    - 기본적인 텍스트, 링크, 리스트, 헤더, 볼드/이탤릭, 줄바꿈을 처리
    - 복잡한 스타일은 단순 텍스트로 폴백
    """

    def __init__(self):
        super().__init__()
        self.parts: List[str] = []
        self.list_stack: List[str] = []
        self.href_stack: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("br",):
            self.parts.append("\n")
        elif tag in ("p", "div"):
            # 단락 시작 시 줄바꿈 보장
            if self.parts and not self.parts[-1].endswith("\n\n"):
                self.parts.append("\n")
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("*")
        elif tag in ("ul", "ol"):
            self.list_stack.append(tag)
        elif tag == "li":
            indent = "  " * (len(self.list_stack) - 1)
            bullet = "- " if (self.list_stack and self.list_stack[-1] == "ul") else "1. "
            # 새 리스트 항목은 줄바꿈 후 시작
            self.parts.append(f"\n{indent}{bullet}")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.parts.append("\n" + "#" * level + " ")
        elif tag == "a":
            href = dict(attrs).get("href", "")
            self.href_stack.append(href)
            self.parts.append("[")

    def handle_endtag(self, tag):
        if tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("*")
        elif tag == "p":
            self.parts.append("\n\n")
        elif tag == "div":
            self.parts.append("\n")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self.parts.append("\n")
        elif tag == "li":
            # 리스트 항목 종료 시 줄바꿈 유지
            self.parts.append("")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n\n")
        elif tag == "a":
            href = self.href_stack.pop() if self.href_stack else ""
            self.parts.append(f"]({href})" if href else "]")

    def handle_data(self, data):
        # 공백 정리 (여러 공백 → 한 칸)
        cleaned = re.sub(r"\s+", " ", data)
        self.parts.append(cleaned)

    def get_markdown(self) -> str:
        text = "".join(self.parts)
        # 중복 줄바꿈 정리
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html: str) -> str:
    """외부 라이브러리 없이 HTML을 단순 Markdown으로 변환"""
    parser = _HTMLToMarkdown()
    parser.feed(html)
    return parser.get_markdown()

def _get_credentials(token_data: Dict[str, Any]) -> Credentials:
    """토큰 데이터를 Google Credentials 객체로 변환"""
    return Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )

def _create_message(to: str, subject: str, body: str, attachment_path: Optional[str] = None) -> Dict[str, str]:
    """이메일 메시지 생성"""
    if attachment_path:
        message = MIMEMultipart()
    else:
        message = MIMEText(body, "plain", "utf-8")
    
    message["to"] = to
    message["subject"] = subject
    
    if attachment_path:
        message.attach(MIMEText(body, "plain", "utf-8"))
        if os.path.exists(attachment_path):
            filename = os.path.basename(attachment_path)
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={filename}")
                message.attach(part)
    
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw_message}

async def send_email(user_id: str, to: str, subject: str, body: str, attachment_path: Optional[str] = None) -> Dict[str, Any]:
    """Gmail로 이메일 전송"""
    print(f"\n📧 [Gmail Tool] 이메일 전송 시작")
    print(f"   - User ID: {user_id}")
    print(f"   - To: {to}")
    print(f"   - Subject: {subject}")
    
    try:
        token_data = await load_token(user_id, "google")
        if not token_data:
            print(f"❌ [Gmail Tool] Google 토큰 로드 실패")
            return {"success": False, "data": None, "error": "Google 토큰을 찾을 수 없습니다."}
        
        print(f"✅ [Gmail Tool] Google 토큰 로드 성공")
        
        creds = _get_credentials(token_data)
        service = build('gmail', 'v1', credentials=creds)
        
        message = _create_message(to, subject, body, attachment_path)
        
        print(f"🚀 [Gmail Tool] Gmail API 전송 요청 중...")
        result = service.users().messages().send(userId='me', body=message).execute()
        
        print(f"✅ [Gmail Tool] 이메일 전송 성공! (ID: {result.get('id')})")
        return {"success": True, "data": {"message_id": result.get('id'), "thread_id": result.get('threadId'), "to": to, "subject": subject}, "error": None}
    except Exception as e:
        import traceback
        print(f"\n🔥 [Gmail Tool] 이메일 전송 중 치명적 오류 발생!")
        print(f"   - Error Type: {type(e).__name__}")
        print(f"   - Error Message: {str(e)}")
        print(f"   - Traceback:")
        traceback.print_exc()
        return {"success": False, "data": None, "error": f"이메일 전송 중 오류: {str(e)}"}

def _decode_body_from_parts(parts: List[Dict[str, Any]]) -> Tuple[str, bool]:
    """MIME 파트를 순회하며 text/plain 또는 text/html 본문을 추출"""
    for part in parts:
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data:
            import base64

            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            if mime_type == "text/html":
                return decoded, True
            if mime_type == "text/plain":
                # html이 없을 경우 대비해서 우선 반환
                return decoded, False
        # 하위 파트 재귀
        if "parts" in part:
            inner, is_html = _decode_body_from_parts(part["parts"])
            if inner:
                return inner, is_html
    return "", False


def _extract_body_and_markdown(service, msg_id: str) -> Tuple[str, str]:
    """Gmail 메시지 본문을 추출하고, HTML이면 Markdown으로 변환"""
    try:
        message = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = message.get("payload", {})

        body_text = ""
        is_html = False

        # 1) 최상위 body 확인
        if "body" in payload and payload["body"].get("data"):
            import base64

            body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
            is_html = payload.get("mimeType", "") == "text/html"
        # 2) 파트 순회
        elif "parts" in payload:
            body_text, is_html = _decode_body_from_parts(payload["parts"])

        # 3) html → markdown 변환 (내장 변환기 사용)
        if is_html and body_text:
            body_markdown = html_to_markdown(body_text)
        else:
            body_markdown = body_text

        return body_text, body_markdown
    except Exception:
        return "", ""


async def list_messages(user_id: str, query: str = "is:unread", limit: int = 5, label_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Gmail 메시지 목록 조회"""
    try:
        token_data = await load_token(user_id, "google")
        if not token_data:
            return {"success": False, "data": None, "error": "Google 토큰을 찾을 수 없습니다."}
        
        creds = _get_credentials(token_data)
        service = build('gmail', 'v1', credentials=creds)
        
        results = service.users().messages().list(userId='me', q=query, maxResults=limit, labelIds=label_ids).execute()
        messages = results.get('messages', [])
        
        message_details = []
        for msg in messages:
            msg_id = msg['id']
            detail = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From', 'Subject', 'Date']).execute()
            headers = {h['name']: h['value'] for h in detail.get('payload', {}).get('headers', [])}

            # 본문 추출 및 markdown 변환
            _, body_markdown = _extract_body_and_markdown(service, msg_id)

            message_details.append({
                "id": msg_id,
                "thread_id": detail.get('threadId'),
                "from": headers.get('From', ''),
                "subject": headers.get('Subject', ''),
                "date": headers.get('Date', ''),
                "snippet": detail.get('snippet', ''),
                "body_markdown": body_markdown,
            })
        
        return {"success": True, "data": {"count": len(message_details), "messages": message_details, "result_size_estimate": results.get('resultSizeEstimate', 0)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": f"메시지 목록 조회 중 오류: {str(e)}"}

async def get_message(user_id: str, message_id: str, format: str = "full") -> Dict[str, Any]:
    """Gmail 메시지 상세 조회"""
    try:
        token_data = await load_token(user_id, "google")
        if not token_data:
            return {"success": False, "data": None, "error": "Google 토큰을 찾을 수 없습니다."}
        
        creds = _get_credentials(token_data)
        service = build('gmail', 'v1', credentials=creds)
        
        message = service.users().messages().get(userId='me', id=message_id, format=format).execute()
        
        headers = {}
        if 'payload' in message and 'headers' in message['payload']:
            headers = {h['name']: h['value'] for h in message['payload']['headers']}
        
        body_text, body_markdown = _extract_body_and_markdown(service, message_id)
        
        return {
            "success": True,
            "data": {
                "id": message.get('id'),
                "thread_id": message.get('threadId'),
                "from": headers.get('From', ''),
                "to": headers.get('To', ''),
                "subject": headers.get('Subject', ''),
                "date": headers.get('Date', ''),
                "snippet": message.get('snippet', ''),
                "body": body_text,
                "body_markdown": body_markdown,
                "label_ids": message.get('labelIds', [])
            },
            "error": None
        }
    except Exception as e:
        return {"success": False, "data": None, "error": f"메시지 조회 중 오류: {str(e)}"}

