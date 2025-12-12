"""
DuckDuckGo 뉴스 검색 모듈
- 글로벌 트렌드 키워드 추출용
- API 키 불필요 (무료)
"""
import os
import time
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


class DuckDuckGoSearcher:
    """DuckDuckGo 뉴스 검색"""
    
    def __init__(self):
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def search_news(
        self, 
        query: str, 
        max_results: int = 5,
        region: str = "wt-wt"  # wt-wt: 전세계, kr-kr: 한국
    ) -> list[dict]:
        """
        DuckDuckGo 뉴스 검색
        
        Args:
            query: 검색어 (영어 권장)
            max_results: 결과 개수
            region: 지역 설정
            
        Returns:
            뉴스 결과 리스트
        """
        try:
            from ddgs import DDGS
            
            # Rate limit 대응: 잠시 대기
            time.sleep(1)
            
            with DDGS() as ddgs:
                # text 검색 사용 (news보다 rate limit 덜함)
                results = list(ddgs.text(
                    query,
                    region=region,
                    max_results=max_results
                ))
                return results
        except ImportError:
            # 구버전 패키지 호환
            try:
                from duckduckgo_search import DDGS
                time.sleep(1)
                with DDGS() as ddgs:
                    results = list(ddgs.text(
                        query,
                        region=region,
                        max_results=max_results
                    ))
                    return results
            except Exception as e:
                print(f"⚠️  DuckDuckGo 검색 실패: {e}")
                return []
        except Exception as e:
            print(f"⚠️  DuckDuckGo 검색 실패: {e}")
            return []
    
    async def extract_trend_keywords(
        self, 
        topic: str,
        num_articles: int = 5
    ) -> list[str]:
        """
        주제 관련 글로벌 트렌드 키워드 추출
        
        Args:
            topic: 주제 (한국어)
            num_articles: 분석할 기사 수
            
        Returns:
            추출된 키워드 리스트
        """
        # 1. 먼저 LLM으로 영어 검색어 생성
        translate_prompt = f"""다음 한국어 주제를 영어 검색어로 변환해주세요.

주제: "{topic}"

규칙:
- 뉴스 검색에 적합한 2-4단어 영어 키워드
- 한 줄로 출력

영어 검색어:"""

        translate_response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": translate_prompt}],
            temperature=0.3,
            max_tokens=30
        )
        
        english_query = translate_response.choices[0].message.content.strip()
        search_query = f"{english_query} trend 2024"
        
        # 2. 뉴스 검색
        results = self.search_news(search_query, max_results=num_articles)
        
        if not results:
            return []
        
        # 3. 기사 제목/설명 수집
        articles_text = []
        for item in results:
            title = item.get("title", "")
            body = item.get("body", "") or item.get("href", "")
            articles_text.append(f"Title: {title}\nContent: {body}")
        
        combined_text = "\n\n".join(articles_text)
        
        # 4. LLM으로 키워드 추출 (한국어로)
        prompt = f"""다음은 "{topic}" 관련 해외 최신 검색 결과입니다.

{combined_text}

위 내용에서 "{topic}"과 관련된 글로벌 트렌드 키워드를 추출해주세요.

규칙:
- 한국어로 번역해서 출력
- 구체적이고 실용적인 키워드만 (예: "숏폼 알고리즘", "바이럴 훅")
- 너무 일반적인 단어 제외
- 5~8개 키워드
- 각 키워드는 쉼표로 구분

키워드:"""

        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        # 5. 키워드 파싱
        keywords_text = response.choices[0].message.content.strip()
        keywords = [k.strip() for k in keywords_text.split(",") if k.strip()]
        
        return keywords


# 테스트용
if __name__ == "__main__":
    import asyncio
    
    async def main():
        searcher = DuckDuckGoSearcher()
        keywords = await searcher.extract_trend_keywords("유튜브 조회수 콘텐츠")
        print("추출된 글로벌 트렌드 키워드:")
        for kw in keywords:
            print(f"  - {kw}")
    
    asyncio.run(main())
