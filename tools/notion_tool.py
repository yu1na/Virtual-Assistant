"""Notion API Tool (공식 SDK 사용)"""
from typing import Optional, Dict, Any, List
import re
from notion_client import AsyncClient
from notion_client.errors import APIResponseError
from .token_manager import load_token
from .notion_utils import blocks_to_markdown, markdown_to_blocks
import traceback

async def create_page(user_id: str, parent_page_id: str, title: str, content: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Notion 페이지 생성"""
    try:
        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        page_data = {
            "parent": {"page_id": parent_page_id},
            "properties": {"title": {"title": [{"text": {"content": title}}]}}
        }
        
        if content:
            page_data["children"] = content
        else:
            page_data["children"] = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}]
        
        result = await notion.pages.create(**page_data)
        
        return {"success": True, "data": {"page_id": result.get("id"), "url": result.get("url"), "created_time": result.get("created_time"), "title": title}, "error": None}
    except APIResponseError as e:
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "data": None, "error": f"페이지 생성 중 오류: {str(e)}"}

async def add_database_item(user_id: str, database_id: str, properties_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Notion 데이터베이스에 항목 추가"""
    try:
        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        result = await notion.pages.create(parent={"database_id": database_id}, properties=properties_dict)
        
        return {"success": True, "data": {"page_id": result.get("id"), "url": result.get("url"), "created_time": result.get("created_time"), "properties": result.get("properties", {})}, "error": None}
    except APIResponseError as e:
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "data": None, "error": f"데이터베이스 항목 추가 중 오류: {str(e)}"}

async def query_database(user_id: str, database_id: str, filter_dict: Optional[Dict] = None, sorts: Optional[List[Dict]] = None, page_size: int = 100) -> Dict[str, Any]:
    """Notion 데이터베이스 쿼리"""
    try:
        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        query_params = {"page_size": page_size}
        if filter_dict:
            query_params["filter"] = filter_dict
        if sorts:
            query_params["sorts"] = sorts
        
        result = await notion.databases.query(database_id=database_id, **query_params)
        
        results = result.get("results", [])
        items = []
        for item in results:
            properties = item.get("properties", {})
            simple_props = {}
            for key, value in properties.items():
                prop_type = value.get("type")
                if prop_type == "title":
                    title_list = value.get("title", [])
                    simple_props[key] = title_list[0].get("text", {}).get("content", "") if title_list else ""
                elif prop_type == "rich_text":
                    text_list = value.get("rich_text", [])
                    simple_props[key] = text_list[0].get("text", {}).get("content", "") if text_list else ""
                elif prop_type == "select":
                    select_obj = value.get("select")
                    simple_props[key] = select_obj.get("name", "") if select_obj else ""
                elif prop_type == "date":
                    date_obj = value.get("date")
                    simple_props[key] = date_obj.get("start", "") if date_obj else ""
                elif prop_type == "number":
                    simple_props[key] = value.get("number")
                elif prop_type == "checkbox":
                    simple_props[key] = value.get("checkbox", False)
            
            items.append({"id": item.get("id"), "url": item.get("url"), "properties": simple_props})
        
        return {"success": True, "data": {"count": len(items), "items": items, "has_more": result.get("has_more", False)}, "error": None}
    except APIResponseError as e:
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "data": None, "error": f"데이터베이스 쿼리 중 오류: {str(e)}"}

async def update_page(user_id: str, page_id: str, properties_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Notion 페이지 속성 업데이트"""
    try:
        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        result = await notion.pages.update(page_id=page_id, properties=properties_dict)
        
        return {"success": True, "data": {"page_id": result.get("id"), "url": result.get("url"), "last_edited_time": result.get("last_edited_time")}, "error": None}
    except APIResponseError as e:
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "data": None, "error": f"페이지 업데이트 중 오류: {str(e)}"}

async def append_block_children(user_id: str, block_id: str, children: List[Dict]) -> Dict[str, Any]:
    """Notion 블록에 자식 블록 추가"""
    try:
        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        result = await notion.blocks.children.append(block_id=block_id, children=children)
        
        return {"success": True, "data": {"results": result.get("results", [])}, "error": None}
    except APIResponseError as e:
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "data": None, "error": f"블록 추가 중 오류: {str(e)}"}


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)

async def _resolve_page_id(user_id: str, page_id_or_title: str) -> Optional[str]:
    """page_id_or_title 이 UUID면 그대로, 아니면 제목 검색해서 Notion page_id로 바꿔준다."""
    if UUID_RE.match(page_id_or_title):
        return page_id_or_title

    search_res = await search_pages(user_id, page_id_or_title, page_size=5)
    if not search_res["success"] or not search_res["data"]["pages"]:
        return None

    pages = search_res["data"]["pages"]

    for p in pages:
        if p.get("title") == page_id_or_title:
            return p["id"]

    return pages[0]["id"]  # fallback


async def get_page_content(user_id: str, page_id: str) -> Dict[str, Any]:
    """
    Notion 페이지 내용을 마크다운으로 가져오기
    
    Args:
        user_id: 사용자 ID
        page_id: Notion 페이지 ID 또는 제목
    
    Returns:
        {"success": bool, "data": {"markdown": str, "title": str}, "error": str}
    """
    try:
        resolved_id = await _resolve_page_id(user_id, page_id)
        if not resolved_id:
            return {
                "success": False,
                "data": None,
                "error": f"페이지 '{page_id}' 를 찾을 수 없습니다.",
            }

        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        # 페이지 정보 가져오기 (제목)
        page = await notion.pages.retrieve(page_id=resolved_id)
        
        # 제목 추출
        title = "Untitled"
        properties = page.get("properties", {})
        for prop_name, prop_value in properties.items():
            if prop_value.get("type") == "title":
                title_array = prop_value.get("title", [])
                if title_array:
                    title = title_array[0].get("text", {}).get("content", "Untitled")
                break
        
        # 페이지 블록 가져오기 (재귀적으로 모든 자식 포함)
        async def _fetch_children_recursive(block_id: str) -> List[Dict]:
            """블록의 자식들을 재귀적으로 가져오는 헬퍼 함수"""
            all_results = []
            try:
                start_cursor = None
                
                # 페이지네이션 처리
                while True:
                    # 페이지 가져오기
                    if start_cursor:
                        response = await notion.blocks.children.list(
                            block_id=block_id,
                            start_cursor=start_cursor
                        )
                    else:
                        response = await notion.blocks.children.list(block_id=block_id)
                    
                    children = response.get("results", [])
                    
                    for child in children:
                        if child.get("has_children", False):
                            block_type = child.get("type")
                            
                            # child_page / child_database는 재귀 진입하지 않고 블록만 보존
                            # child_page는 하위 페이지를 나타내므로, 그 내용을 가져오지 않고 제목만 표시
                            if block_type not in ["child_page", "child_database"]:
                                # 토글(또는 토글 가능한 헤더)은 계속 진입
                                is_toggle_header = (
                                    block_type in ["heading_1", "heading_2", "heading_3"]
                                    and child.get(block_type, {}).get("is_toggleable", False)
                                )
                                if block_type == "toggle" or is_toggle_header:
                                    child_blocks = await _fetch_children_recursive(child["id"])
                                    child["children"] = child_blocks
                                else:
                                    # 기타 has_children 블록도 기존처럼 재귀
                                    child_blocks = await _fetch_children_recursive(child["id"])
                                    child["children"] = child_blocks
                        
                        all_results.append(child)
                    
                    # 다음 페이지가 없으면 종료
                    if not response.get("has_more"):
                        break
                    
                    # 다음 페이지 커서 설정
                    start_cursor = response.get("next_cursor")
                    if not start_cursor:
                        break
                    
            except Exception as e:
                print(f"[WARNING] 자식 블록 가져오기 실패 (ID: {block_id}): {e}")
                import traceback
                traceback.print_exc()
                
            return all_results

        # 최상위 블록 가져오기
        blocks = await _fetch_children_recursive(resolved_id)
        
        # 하위 페이지만 있는지 확인 (블록 레벨에서 체크)
        def has_only_child_pages(blocks_list: List[Dict]) -> bool:
            """블록 리스트가 child_page만 포함하는지 확인"""
            if not blocks_list:
                return False
            
            for block in blocks_list:
                block_type = block.get("type")
                # child_page가 아니면 내용이 있는 것
                if block_type != "child_page":
                    return False
                # child_page인 경우 자식 블록이 없어야 함 (이미 재귀 진입하지 않았으므로)
                if block.get("children"):
                    # child_page에 자식이 있으면 그것은 다른 블록 타입일 가능성이 있음
                    if not has_only_child_pages(block.get("children", [])):
                        return False
            
            return True
        
        is_only_child_pages = has_only_child_pages(blocks)
        
        # 마크다운으로 변환
        markdown = blocks_to_markdown(blocks)
        
        return {
            "success": True,
            "data": {
                "markdown": markdown,
                "title": title,
                "page_id": resolved_id,
                "is_only_child_pages": is_only_child_pages  # 메타데이터 추가
            },
            "error": None
        }
    except APIResponseError as e:
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "data": None, "error": f"페이지 내용 가져오기 중 오류: {str(e)}"}


async def search_pages(user_id: str, query: str, page_size: int = 10) -> Dict[str, Any]:
    """
    Notion 페이지 검색
    
    Args:
        user_id: 사용자 ID
        query: 검색 쿼리
        page_size: 결과 개수
    
    Returns:
        {"success": bool, "data": {"pages": List}, "error": str}
    """
    try:
        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        # Notion 검색 API 호출
        search_response = await notion.search(
            query=query,
            filter={"property": "object", "value": "page"},
            page_size=page_size
        )
        
        results = search_response.get("results", [])
        pages = []
        
        for page in results:
            page_id = page.get("id")
            
            # 제목 추출
            title = "Untitled"
            properties = page.get("properties", {})
            for prop_name, prop_value in properties.items():
                if prop_value.get("type") == "title":
                    title_array = prop_value.get("title", [])
                    if title_array:
                        title = title_array[0].get("text", {}).get("content", "Untitled")
                    break
            
            pages.append({
                "id": page_id,
                "title": title,
                "url": page.get("url", "")
            })
        
        return {
            "success": True,
            "data": {
                "pages": pages,
                "count": len(pages)
            },
            "error": None
        }
    except APIResponseError as e:
        traceback.print_exc()
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "data": None, "error": f"페이지 검색 중 오류: {str(e)}"}


async def create_page_from_markdown(user_id: str, parent_id: str, title: str, markdown: str) -> Dict[str, Any]:
    """
    마크다운 내용으로 Notion 페이지 생성
    
    Args:
        user_id: 사용자 ID
        parent_id: 부모 페이지 ID
        title: 페이지 제목
        markdown: 마크다운 내용
    
    Returns:
        {"success": bool, "data": {"page_id": str, "url": str}, "error": str}
    """
    try:
        token_data = await load_token(user_id, "notion")
        if not token_data:
            return {"success": False, "data": None, "error": "Notion 토큰을 찾을 수 없습니다."}
        
        access_token = token_data.get("access_token")
        notion = AsyncClient(auth=access_token)
        
        # 마크다운을 Notion 블록으로 변환
        blocks = markdown_to_blocks(markdown)
        
        # 페이지 생성
        page_data = {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            },
            "children": blocks[:100]  # Notion API는 한 번에 최대 100개 블록만 허용
        }
        
        result = await notion.pages.create(**page_data)
        
        return {
            "success": True,
            "data": {
                "page_id": result.get("id"),
                "url": result.get("url"),
                "title": title
            },
            "error": None
        }
    except APIResponseError as e:
        return {"success": False, "data": None, "error": f"Notion API 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "data": None, "error": f"페이지 생성 중 오류: {str(e)}"}


# ============================================
# 전체 페이지 인덱스 헬퍼 (유저별 캐시)
# ============================================

_page_index_cache: dict[str, list[dict]] = {}


async def list_all_pages(user_id: str) -> list[dict]:
    """
    해당 유저 워크스페이스의 모든 페이지 메타데이터(id, title, url)를 가져옵니다.
    Notion search API를 사용하여 페이지 전체를 페이징하며 수집합니다.
    """
    token_data = await load_token(user_id, "notion")
    if not token_data:
        return []
    
    access_token = token_data.get("access_token")
    notion = AsyncClient(auth=access_token)

    results = []
    start_cursor = None

    while True:
        resp = await notion.search(
            **{
                "query": "",
                "filter": {"property": "object", "value": "page"},
                "start_cursor": start_cursor,
                "page_size": 100,
            }
        )
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")

    pages: list[dict] = []
    for p in results:
        title = ""
        properties = p.get("properties", {})
        # title 속성 찾기
        for prop_name, prop_value in properties.items():
            if prop_value.get("type") == "title":
                title_array = prop_value.get("title", [])
                if title_array:
                    title = title_array[0].get("text", {}).get("content", "")
                break

        pages.append(
            {
                "id": p["id"],
                "title": title,
                "url": p.get("url"),
            }
        )

    return pages


async def get_or_build_page_index(user_id: str, force_reload: bool = False) -> list[dict]:
    """
    유저별 전체 페이지 인덱스를 캐시에 저장하고 재사용합니다.
    force_reload=True면 Notion에서 다시 전체 조회합니다.
    """
    global _page_index_cache

    if (not force_reload) and (user_id in _page_index_cache):
        return _page_index_cache[user_id]

    pages = await list_all_pages(user_id)
    _page_index_cache[user_id] = pages
    return pages