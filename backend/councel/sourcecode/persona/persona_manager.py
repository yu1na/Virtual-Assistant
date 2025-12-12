"""
페르소나 관리 모듈
생성날짜: 2025.12.01
설명: RAG 기반 페르소나 생성 및 관리 기능
시간복잡도: O(p + q*n + m)
"""

import json
import time
import asyncio
from pathlib import Path
from typing import Optional
from threading import Thread
from openai import OpenAI
from openai import AsyncOpenAI

# 페르소나 생성 및 관리 클래스
class PersonaManager:
    
    # 초기화 함수
    def __init__(self, openai_client: OpenAI, collection, base_dir: Path, async_openai_client: Optional[AsyncOpenAI] = None):

        # OpenAI, 컬렉션, 기본 경로 설정
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
        self.collection = collection
        self.base_dir = base_dir
        
        # 캐시 파일 경로 설정
        cache_dir = base_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        self.persona_cache_path = cache_dir / "adler_persona_cache.json"
        
        # 페르소나 상태 플래그(기본값)
        self._persona_ready = False
        self._rag_persona_ready = False
        self.adler_persona = None
        
        # 캐시된 페르소나 로드 시도
        cached_persona = self._load_cached_persona()
        if cached_persona:
            self.adler_persona = cached_persona
            self._persona_ready = True
            self._rag_persona_ready = True
        else:
            # 기본 페르소나로 빠르게 시작
            self.adler_persona = self._get_default_persona()
            self._persona_ready = True
            self._rag_persona_ready = False
            print("[정보] 기본 페르소나로 시작 (백그라운드에서 RAG 페르소나 생성 중...)")
            # 백그라운드에서 RAG 페르소나 생성
            self._start_background_persona_generation()
    
    # RAG 기반 페르소나 생성(Vector DB + 웹 검색)
    def generate_persona_with_rag(self) -> str:
        return self._generate_persona_from_rag()
    
    # 프롬프트 엔지니어링으로 페르소나 생성(기본 페르소나)
    def generate_persona_with_prompt_engineering(self) -> str:

        return """

            당신은 알프레드 아들러(Alfred Adler)의 개인심리학을 따르는 공감적인 심리학자이며,
            EAP(Employee Assistance Program)와 SFBT(Solution-Focused Brief Therapy) 기법을 통합하여 상담합니다.

            핵심 원칙:
            1. 열등감과 보상: 모든 인간은 열등감을 느끼며, 이를 극복하려는 우월성 추구가 성장의 동력입니다.
            2. 사회적 관심: 인간은 본질적으로 사회적 존재이며, 공동체 감각이 중요합니다.
            3. 생활양식: 개인의 독특한 생활양식이 행동과 사고를 결정합니다.
            4. 목적론적 관점: 과거보다는 미래의 목표가 현재 행동을 결정합니다.
            5. 격려: 용기를 북돋우는 것이 치료의 핵심입니다.
            6. 해결 중심: 문제보다는 해결책과 강점에 초점을 맞춥니다. (SFBT)
            7. 단기 개입: 즉각적이고 실천 가능한 지원을 제공합니다. (EAP)

            답변 방식 (2단계 구조):
            1단계 - 감정 인정 및 공감 (아들러 + EAP):
               - 먼저 상대방의 감정을 있는 그대로 인정하고 공감합니다.
               - "~하셨군요", "~느끼시는군요", "~한 마음이 드셨겠어요"
               - 감정을 판단하지 않고 있는 그대로 받아들입니다.
               - 상황의 심각도를 파악하고 필요시 즉각적 지원을 고려합니다.
            
            2단계 - 자연스러운 질문 또는 공감문 (아들러 + SFBT):
               - 상황에 맞는 자연스러운 질문이나 공감을 제시합니다.
               - 고정된 질문이 아니라 사용자의 상황에 맞게 자연스럽게 질문합니다.
               - SFBT 원칙에 따라 강점, 자원, 해결책을 탐색하도록 돕습니다.
               - 사용자가 스스로 답을 찾을 수 있도록 격려합니다.

            말투:
            - 따뜻하고 수용적인 톤 유지
            - 경청하고 있음을 느끼게 하는 표현 사용
            - "~하셨군요", "~느끼시는군요" 등 반영적 경청 기법 활용
            - 판단하지 않고 이해하려는 자세
            - 1~2문장으로 간결하되 공감과 희망이 느껴지도록 작성

            중요사항:
            - 반드시 감정 인정 → 자연스러운 질문 순서로 답변
            - 상대방의 감정을 최소화하거나 무시하지 않기
            - "하지만", "그래도" 등 감정을 부정하는 표현 자제
            - 상대방이 자신의 감정을 충분히 표현했다고 느끼게 하기
            - 문제보다는 해결책, 약점보다는 강점에 초점
            - 사용자의 자율성과 주도성을 존중
            - 고정된 질문이 아니라 상황에 맞는 자연스러운 질문을 하세요

        """
    
    # 페르소나 디폴트 값(프롬프트 엔지니어링으로 만든 페르소나)
    def _get_default_persona(self) -> str:
        return self.generate_persona_with_prompt_engineering()
    
    # 저장된 페르소나 캐시 로드(캐시는 24시간 동안 유효)
    def _load_cached_persona(self) -> Optional[str]:

        try:
            if self.persona_cache_path.exists():
                with open(self.persona_cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 캐시 유효성 검사 (24시간 이내)
                    cache_timestamp = data.get('timestamp', 0)
                    current_time = time.time()
                    if current_time - cache_timestamp < 86400:  # 24시간 = 86400초
                        return data.get('persona')
                    else:
                        print(f"[정보] 캐시가 만료되었습니다")
        except Exception as e:
            print(f"[경고] 캐시 로드 실패: {e}")
        return None
    
    # 페르소나를 캐시에 저장
    def _save_persona_cache(self, persona: str):

        try:
            data = {
                'persona': persona,
                'timestamp': time.time()
            }
            with open(self.persona_cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[경고] 캐시 저장 실패: {e}")
    
    # 백그라운드에서 RAG 페르소나 생성 및 캐싱
    def _start_background_persona_generation(self):

        # 백그라운드에서 실행하는 함수
        def generate_in_background():
            try:
                # 새 이벤트 루프 생성하여 비동기 함수 실행
                rag_persona = asyncio.run(self._generate_persona_from_rag())
                self.adler_persona = rag_persona
                self._rag_persona_ready = True
                self._save_persona_cache(rag_persona)
                print("[정보] RAG 페르소나 로딩 완료!")
            except Exception as e:
                print(f"[경고] 백그라운드 페르소나 생성 실패: {e}")
                print("[정보] 기본 페르소나를 계속 사용합니다.")
                import traceback
                traceback.print_exc()
        
        # 백그라운드 스레드 시작 (daemon=True로 서버 종료 시 자동 정리)
        thread = Thread(target=generate_in_background, daemon=True)
        thread.start()
    
    # 페르소나 준비 여부 확인 함수
    def is_rag_persona_ready(self) -> bool:
        return self._rag_persona_ready
    
    # 웹 검색 -> 아들러 정보 수집(페르소나 생성 용도)
    async def _search_web_for_adler(self) -> str:
 
        try:
            if self.async_openai_client:
                response = await self.async_openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert on Alfred Adler's individual psychology. Provide a comprehensive summary of Adler's core principles and therapeutic approaches."
                        },
                        {
                            "role": "user",
                            "content": """Provide a detailed summary of Alfred Adler's individual psychology including:
1. Core principles (inferiority complex, superiority striving, social interest, etc.)
2. Lifestyle and life patterns
3. Therapeutic techniques and encouragement methods
4. Teleological perspective and goal orientation
5. Key concepts for counseling practice

Keep it concise but comprehensive."""
                        }
                    ],
                    temperature=0.3,
                    max_tokens=800
                )
            else:
                # Fallback: 동기 클라이언트 사용
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert on Alfred Adler's individual psychology. Provide a comprehensive summary of Adler's core principles and therapeutic approaches."
                        },
                        {
                            "role": "user",
                            "content": """Provide a detailed summary of Alfred Adler's individual psychology including:
1. Core principles (inferiority complex, superiority striving, social interest, etc.)
2. Lifestyle and life patterns
3. Therapeutic techniques and encouragement methods
4. Teleological perspective and goal orientation
5. Key concepts for counseling practice

Keep it concise but comprehensive."""
                        }
                    ],
                    temperature=0.3,
                    max_tokens=800
                )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[경고] 웹 검색 실패: {e}")
            return ""
    
    # RAG 사용 -> 페르소나 생성 함수
    async def _generate_persona_from_rag(self) -> str:

        # 검색 쿼리 최적화: 6개 → 3개로 축소 (핵심 개념만 선별)
        persona_queries = [
            "Alfred Adler individual psychology core principles",
            "inferiority complex and superiority striving",
            "social interest and community feeling"
        ]
        
        # 1. Vector DB에서 관련 청크 수집 (병렬 처리)
        async def search_query(query: str):
            
            try:
                # 임베딩 생성
                if self.async_openai_client:
                    embedding_response = await self.async_openai_client.embeddings.create(
                        model="text-embedding-3-large",
                        input=query
                    )
                else:
                    # Fallback: 동기 클라이언트 사용 (스레드 풀에서 실행)
                    embedding_response = await asyncio.to_thread(
                        self.openai_client.embeddings.create,
                        model="text-embedding-3-large",
                        input=query
                    )
                query_embedding = embedding_response.data[0].embedding
                
                # 검색 (ChromaDB는 동기식이므로 스레드 풀에서 실행)
                results = await asyncio.to_thread(
                    self.collection.query,
                    query_embeddings=[query_embedding],
                    n_results=3
                )
                
                # 결과 포맷팅
                chunks = []
                if results['ids'] and results['ids'][0]:
                    for i in range(len(results['ids'][0])):
                        chunk = {
                            'id': results['ids'][0][i],
                            'text': results['documents'][0][i],
                            'metadata': results['metadatas'][0][i],
                            'distance': results['distances'][0][i] if 'distances' in results else None
                        }
                        chunks.append(chunk)
                return chunks
            except Exception as e:
                print(f"[경고] 페르소나 생성 중 검색 실패 ({query}): {e}")
                return []
        
        # 3개 쿼리를 병렬로 처리
        search_tasks = [search_query(query) for query in persona_queries]
        search_results = await asyncio.gather(*search_tasks)
        
        # 결과 병합
        all_chunks = []
        for chunks in search_results:
            all_chunks.extend(chunks)
        
        # 중복 제거 (id 기준)
        seen_ids = set()
        unique_chunks = []
        for chunk in all_chunks:
            if chunk['id'] not in seen_ids:
                seen_ids.add(chunk['id'])
                unique_chunks.append(chunk)
        
        # 상위 5개 청크만 사용 -> 10개에서 5개로 축소 -> 속도 줄이기 위함
        unique_chunks = unique_chunks[:5]
        
        # 2. 웹 검색으로 최신 정보 수집 (Vector DB 검색과 병렬 처리)
        web_info_task = self._search_web_for_adler()
        
        # Vector DB 청크 처리와 웹 검색을 병렬로 대기
        web_info = await web_info_task
        
        # 3. 검색된 청크가 없으면 기본 페르소나 사용
        if not unique_chunks and not web_info:
            return self._get_default_persona()
        
        # 4. Vector DB 청크 텍스트 추출
        context_parts = []
        if unique_chunks:
            context_parts.append("=== Vector DB 자료 ===")
            for i, chunk in enumerate(unique_chunks, 1):
                context_parts.append(f"[자료 {i}] {chunk['text'][:500]}")  # 각 청크 최대 500자
        
        # 5. 웹 검색 정보 추가
        if web_info:
            context_parts.append("\n=== 웹 검색 정보 ===")
            context_parts.append(web_info)
        
        context = "\n\n".join(context_parts)
        
        # 6. LLM을 사용하여 페르소나 프롬프트 생성
        try:
            if self.async_openai_client:
                response = await self.async_openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a prompt engineering expert. Create a persona prompt for a therapist based on Adler's individual psychology."
                        },
                        {
                            "role": "user",
                            "content": f"""다음은 알프레드 아들러의 개인심리학에 관한 자료입니다:

                        {context}

                        위 자료를 바탕으로 다음 형식으로 페르소나 프롬프트를 작성해주세요:

                        **형식:**
                        당신은 알프레드 아들러(Alfred Adler)의 개인심리학을 따르는 공감적인 심리학자이며,
                        EAP(Employee Assistance Program)와 SFBT(Solution-Focused Brief Therapy) 기법을 통합하여 상담합니다.

                        핵심 원칙:
                        1. [아들러 원칙 1]
                        2. [아들러 원칙 2]
                        3. [아들러 원칙 3]
                        4. [아들러 원칙 4]
                        5. [아들러 원칙 5]
                        6. 해결 중심: 문제보다는 해결책과 강점에 초점을 맞춥니다. (SFBT)
                        7. 단기 개입: 즉각적이고 실천 가능한 지원을 제공합니다. (EAP)

                        답변 방식 (2단계 구조):
                        1단계 - 감정 인정 및 공감 (아들러 + EAP): [감정 인정 및 상황 평가 방법]
                        2단계 - 자연스러운 질문 또는 공감문 (아들러 + SFBT): [상황에 맞는 질문 방법]

                        말투:
                        - 따뜻하고 수용적인 톤
                        - 반영적 경청 기법 ("~하셨군요", "~느끼시는군요")
                        - 판단하지 않고 이해하려는 자세
                        - [추가 말투 특징]

                        **중요 사항:**
                        - 반드시 감정 인정 → 자연스러운 질문 순서로 답변
                        - 상대방의 감정을 최소화하거나 무시하지 않기
                        - "하지만", "그래도" 등 감정을 부정하는 표현 자제
                        - 사회적 관심과 공동체 감각 강조
                        - 목표 지향적 관점 제시
                        - 문제보다는 해결책, 약점보다는 강점에 초점 (SFBT)
                        - 구체적이고 실천 가능한 단기 전략 제시 (EAP)
                        - 1~2문장으로 간결하되 공감과 희망이 느껴지도록 작성
                        - 공감적 경청을 최우선으로 하되 아들러 이론과 EAP/SFBT 통합
                        - 사용자의 자율성과 주도성을 존중
                        - 고정된 질문이 아니라 상황에 맞는 자연스러운 질문을 하세요

                        페르소나 프롬프트만 출력해주세요. 다른 설명은 불필요합니다."""
                        }
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
            else:
                # Fallback: 동기 클라이언트 사용
                response = await asyncio.to_thread(
                    self.openai_client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a prompt engineering expert. Create a persona prompt for a therapist based on Adler's individual psychology."
                        },
                        {
                            "role": "user",
                            "content": f"""다음은 알프레드 아들러의 개인심리학에 관한 자료입니다:

                        {context}

                        위 자료를 바탕으로 다음 형식으로 페르소나 프롬프트를 작성해주세요:

                        **형식:**
                        당신은 알프레드 아들러(Alfred Adler)의 개인심리학을 따르는 공감적인 심리학자이며,
                        EAP(Employee Assistance Program)와 SFBT(Solution-Focused Brief Therapy) 기법을 통합하여 상담합니다.

                        핵심 원칙:
                        1. [아들러 원칙 1]
                        2. [아들러 원칙 2]
                        3. [아들러 원칙 3]
                        4. [아들러 원칙 4]
                        5. [아들러 원칙 5]
                        6. 해결 중심: 문제보다는 해결책과 강점에 초점을 맞춥니다. (SFBT)
                        7. 단기 개입: 즉각적이고 실천 가능한 지원을 제공합니다. (EAP)

                        답변 방식 (2단계 구조):
                        1단계 - 감정 인정 및 공감 (아들러 + EAP): [감정 인정 및 상황 평가 방법]
                        2단계 - 자연스러운 질문 또는 공감문 (아들러 + SFBT): [상황에 맞는 질문 방법]

                        말투:
                        - 따뜻하고 수용적인 톤
                        - 반영적 경청 기법 ("~하셨군요", "~느끼시는군요")
                        - 판단하지 않고 이해하려는 자세
                        - [추가 말투 특징]

                        **중요 사항:**
                        - 반드시 감정 인정 → 자연스러운 질문 순서로 답변
                        - 상대방의 감정을 최소화하거나 무시하지 않기
                        - "하지만", "그래도" 등 감정을 부정하는 표현 자제
                        - 사회적 관심과 공동체 감각 강조
                        - 목표 지향적 관점 제시
                        - 문제보다는 해결책, 약점보다는 강점에 초점 (SFBT)
                        - 구체적이고 실천 가능한 단기 전략 제시 (EAP)
                        - 1~2문장으로 간결하되 공감과 희망이 느껴지도록 작성
                        - 공감적 경청을 최우선으로 하되 아들러 이론과 EAP/SFBT 통합
                        - 사용자의 자율성과 주도성을 존중
                        - 고정된 질문이 아니라 상황에 맞는 자연스러운 질문을 하세요

                        페르소나 프롬프트만 출력해주세요. 다른 설명은 불필요합니다."""
                        }
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
            
            generated_persona = response.choices[0].message.content.strip()
            return generated_persona
            
        except Exception as e:
            print(f"[경고] 페르소나 생성 실패, 기본 페르소나 사용: {e}")
            return self._get_default_persona()