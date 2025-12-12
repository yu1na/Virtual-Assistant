"""네이버 뉴스 API 테스트"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

import httpx

async def test():
    cid = os.getenv('NAVER_SEARCH_CLIENT_ID')
    cse = os.getenv('NAVER_SEARCH_CLIENT_SECRET')
    
    if not cid or not cse:
        print("ENV 없음!")
        return
    
    print(f"ID: {cid[:5]}... / Secret: {cse[:3]}...")
    
    headers = {'X-Naver-Client-Id': cid, 'X-Naver-Client-Secret': cse}
    params = {'query': '디저트 트렌드', 'display': 3}
    
    async with httpx.AsyncClient() as client:
        r = await client.get('https://openapi.naver.com/v1/search/news.json', headers=headers, params=params)
        print(f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            print(f"Total: {data.get('total')}")
            for item in data.get('items', []):
                title = item.get('title', '').replace('<b>', '').replace('</b>', '')
                print(f"- {title[:50]}")
        else:
            print(f"Error: {r.text}")

if __name__ == "__main__":
    asyncio.run(test())
