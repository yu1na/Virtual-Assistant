"""
네이버 데이터랩 API 연동 모듈
- 검색어 트렌드 분석
- 같은 네이버 API 키 사용
"""
import os
import httpx
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


class NaverDataLabSearcher:
    """네이버 데이터랩 검색어 트렌드 API"""
    
    BASE_URL = "https://openapi.naver.com/v1/datalab/search"
    
    def __init__(self):
        self.client_id = os.getenv("NAVER_SEARCH_CLIENT_ID")
        self.client_secret = os.getenv("NAVER_SEARCH_CLIENT_SECRET")
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if not self.client_id or not self.client_secret:
            raise ValueError("NAVER_SEARCH_CLIENT_ID, NAVER_SEARCH_CLIENT_SECRET 환경변수 필요")
    
    async def get_search_trend(
        self,
        keywords: list[str],
        start_date: str = None,
        end_date: str = None,
        time_unit: str = "month"  # date, week, month
    ) -> dict:
        """
        검색어 트렌드 조회
        
        Args:
            keywords: 검색어 리스트 (최대 5개)
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            time_unit: 시간 단위
            
        Returns:
            트렌드 데이터
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json"
        }
        
        # 키워드 그룹 생성 (각 키워드를 개별 그룹으로)
        keyword_groups = [
            {"groupName": kw, "keywords": [kw]}
            for kw in keywords[:5]  # 최대 5개
        ]
        
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": keyword_groups
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.BASE_URL,
                headers=headers,
                json=body
            )
            response.raise_for_status()
            return response.json()
    
    async def extract_trend_keywords(
        self, 
        topic: str
    ) -> list[str]:
        """
        주제 관련 트렌드 키워드 추출
        
        1. LLM으로 관련 키워드 5개 생성
        2. 데이터랩에서 트렌드 조회
        3. 상승세인 키워드 + 검색량 높은 키워드 반환
        
        Args:
            topic: 주제
            
        Returns:
            트렌드 키워드 리스트
        """
        # 1. LLM으로 관련 키워드 생성
        expand_prompt = f"""다음 주제와 관련된 검색 키워드 5개를 생성해주세요.

주제: "{topic}"

규칙:
- 네이버에서 실제로 검색될 만한 키워드
- 2-4 단어 이내
- 서로 다른 관점의 키워드 (동의어 X)
- 쉼표로 구분해서 한 줄로 출력

키워드:"""

        expand_response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": expand_prompt}],
            temperature=0.7,
            max_tokens=100
        )
        
        keywords_text = expand_response.choices[0].message.content.strip()
        keywords = [k.strip() for k in keywords_text.split(",") if k.strip()][:5]
        
        if not keywords:
            return []
        
        # 2. 데이터랩에서 트렌드 조회
        try:
            trend_data = await self.get_search_trend(keywords)
        except Exception as e:
            print(f"⚠️  데이터랩 API 호출 실패: {e}")
            return keywords  # API 실패 시 그냥 키워드 반환
        
        # 3. 트렌드 분석 (최근 검색량 기준 정렬)
        result_keywords = []
        
        if trend_data.get("results"):
            keyword_scores = []
            
            for result in trend_data["results"]:
                keyword = result.get("title", "")
                data_points = result.get("data", [])
                
                if data_points:
                    # 최근 3개월 평균 vs 전체 평균 비교
                    all_ratios = [d.get("ratio", 0) for d in data_points]
                    recent_ratios = all_ratios[-3:] if len(all_ratios) >= 3 else all_ratios
                    
                    avg_all = sum(all_ratios) / len(all_ratios) if all_ratios else 0
                    avg_recent = sum(recent_ratios) / len(recent_ratios) if recent_ratios else 0
                    
                    # 상승률 계산
                    growth = (avg_recent - avg_all) / avg_all * 100 if avg_all > 0 else 0
                    
                    keyword_scores.append({
                        "keyword": keyword,
                        "recent_avg": avg_recent,
                        "growth": growth
                    })
            
            # 상승률 + 검색량 기준 정렬
            keyword_scores.sort(key=lambda x: (x["growth"], x["recent_avg"]), reverse=True)
            result_keywords = [ks["keyword"] for ks in keyword_scores]
        
        # 4. 추가로 LLM이 생성한 연관 키워드도 포함
        related_prompt = f"""다음 키워드들과 연관된 최신 트렌드 키워드를 5개 더 생성해주세요.

기존 키워드: {', '.join(result_keywords)}
주제: "{topic}"

규칙:
- 위 키워드와 연관되지만 다른 키워드
- 최신 트렌드 반영
- 쉼표로 구분

추가 키워드:"""

        related_response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": related_prompt}],
            temperature=0.7,
            max_tokens=100
        )
        
        related_text = related_response.choices[0].message.content.strip()
        related_keywords = [k.strip() for k in related_text.split(",") if k.strip()]
        
        # 합치고 중복 제거
        all_keywords = result_keywords + related_keywords
        unique_keywords = list(dict.fromkeys(all_keywords))
        
        # 정제 (번호, 따옴표, 접두사 제거)
        cleaned = []
        for kw in unique_keywords:
            kw = kw.strip()
            # "1. ", "2. " 등 번호 제거
            if kw and kw[0].isdigit() and '.' in kw[:3]:
                kw = kw.split('.', 1)[1].strip()
            # 따옴표 제거
            kw = kw.strip('"\'')
            # "키워드:" 접두사 제거
            if kw.startswith('키워드:'):
                kw = kw[4:].strip()
            if kw:
                cleaned.append(kw)
        
        return cleaned[:10]


# 테스트용
if __name__ == "__main__":
    import asyncio
    
    async def main():
        searcher = NaverDataLabSearcher()
        keywords = await searcher.extract_trend_keywords("유튜브 구독자 늘리기")
        print("추출된 데이터랩 트렌드 키워드:")
        for kw in keywords:
            print(f"  - {kw}")
    
    asyncio.run(main())
