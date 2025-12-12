"""
네이버 뉴스 검색 API 연동 모듈
- 트렌드 키워드 추출용
"""
import os
import re
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


class NaverNewsSearcher:
    """네이버 뉴스 검색 API"""
    
    BASE_URL = "https://openapi.naver.com/v1/search/news.json"
    
    def __init__(self):
        self.client_id = os.getenv("NAVER_SEARCH_CLIENT_ID")
        self.client_secret = os.getenv("NAVER_SEARCH_CLIENT_SECRET")
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if not self.client_id or not self.client_secret:
            raise ValueError("NAVER_SEARCH_CLIENT_ID, NAVER_SEARCH_CLIENT_SECRET 환경변수 필요")
    
    def _clean_html(self, text: str) -> str:
        """HTML 태그 제거"""
        return re.sub(r'<[^>]+>', '', text)
    
    async def search(
        self, 
        query: str, 
        display: int = 10,
        sort: str = "sim"  # sim: 정확도순, date: 날짜순
    ) -> dict:
        """
        네이버 뉴스 검색
        
        Args:
            query: 검색어
            display: 결과 개수 (최대 100)
            sort: 정렬 방식
            
        Returns:
            검색 결과 dict
        """
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        
        params = {
            "query": query,
            "display": display,
            "sort": sort
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.BASE_URL,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def extract_trend_keywords(
        self, 
        topic: str,
        num_articles: int = 5
    ) -> list[str]:
        """
        주제 관련 트렌드 키워드 추출
        
        Args:
            topic: 주제 (예: "파티쉐 디저트")
            num_articles: 분석할 기사 수
            
        Returns:
            추출된 키워드 리스트
        """
        # 0. 먼저 LLM으로 검색어 정제
        refine_prompt = f"""다음 주제에서 네이버 뉴스 검색에 적합한 핵심 키워드 2-3개를 추출해주세요.

주제: "{topic}"

규칙:
- 검색에 적합한 짧은 명사 위주
- 너무 일반적이지 않게 (예: "아이디어" X)
- 쉼표로 구분해서 한 줄로 출력
- 예시: "유튜버 조회수, 콘텐츠 기획" 또는 "디저트 카페, 창업"

키워드:"""

        refine_response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": refine_prompt}],
            temperature=0.3,
            max_tokens=50
        )
        
        refined_query = refine_response.choices[0].message.content.strip()
        # 첫 번째 키워드만 사용 (가장 핵심)
        main_keyword = refined_query.split(",")[0].strip()
        
        # 1. 뉴스 검색
        search_query = f"{main_keyword} 트렌드"
        result = await self.search(search_query, display=num_articles, sort="date")
        
        if not result.get("items"):
            # 검색 실패 시 원본으로 재시도
            result = await self.search(f"{topic[:20]} 트렌드", display=num_articles, sort="date")
            if not result.get("items"):
                return []
        
        # 2. 기사 제목/설명 수집
        articles_text = []
        for item in result["items"]:
            title = self._clean_html(item.get("title", ""))
            desc = self._clean_html(item.get("description", ""))
            articles_text.append(f"제목: {title}\n내용: {desc}")
        
        combined_text = "\n\n".join(articles_text)
        
        # 3. LLM으로 키워드 추출
        prompt = f"""다음은 "{topic}" 관련 최신 뉴스 기사들입니다.

{combined_text}

위 기사들에서 "{topic}"과 관련된 최신 트렌드 키워드를 추출해주세요.

규칙:
- 구체적이고 실용적인 키워드만 (예: "두바이 초콜릿", "약과 크루아상")
- 너무 일반적인 단어 제외 (예: "맛있는", "인기", "트렌드")
- 브랜드명, 신제품명, 새로운 조합 등 포함
- 5~10개 키워드
- 각 키워드는 쉼표로 구분

키워드:"""

        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        # 4. 키워드 파싱
        keywords_text = response.choices[0].message.content.strip()
        keywords = [k.strip() for k in keywords_text.split(",") if k.strip()]
        
        return keywords


# 테스트용
if __name__ == "__main__":
    import asyncio
    
    async def main():
        searcher = NaverNewsSearcher()
        keywords = await searcher.extract_trend_keywords("디저트")
        print("추출된 트렌드 키워드:")
        for kw in keywords:
            print(f"  - {kw}")
    
    asyncio.run(main())
