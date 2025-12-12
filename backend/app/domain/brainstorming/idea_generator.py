"""
아이디어 생성 도구 (Idea Generator)

전체 플로우:
1. Q1: 목적/도메인 입력 ("어디에 쓸 아이디어가 필요하신가요?")
2. Q2: LLM 기반 워밍업 질문 생성 (2-3개) + "네" 입력 대기
3. Q3: 자유연상 입력 (20초 제한, 10개 미만 시 재입력)
4. 임시 RAG 처리:
   - Q3 임베딩 및 임시 ChromaDB 저장
   - Q1-Q3 유사도 기반 키워드 추출
   - 영구 RAG (SCAMPER, Mind Mapping, Starbursting)와 결합
   - LLM으로 아이디어 2-3개 생성
   - 각 아이디어별 SWOT 또는 How Now Wow 분석
5. 삭제 확인 ("삭제하시겠습니까?") - "네" 입력 시 모든 임시 데이터 삭제
"""

import readline  # 한글 입력 백스페이스 버그 수정
import time
import signal
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv
import os

from session_manager import SessionManager
from ephemeral_rag import EphemeralRAG
from domain_hints import get_domain_hint, format_hint_for_prompt
from search.naver_news import NaverNewsSearcher
from search.duckduckgo import DuckDuckGoSearcher
from search.naver_datalab import NaverDataLabSearcher

# ChromaDB import
import chromadb
from chromadb.config import Settings as ChromaSettings


class TimeoutException(Exception):
    """시간 초과 예외"""
    pass


def timeout_handler(signum, frame):
    """시간 초과 핸들러"""
    raise TimeoutException()


class IdeaGenerator:
    """
    아이디어 생성 도구 메인 클래스
    
    Q1 → Q2 → Q3 → 아이디어 생성 → 분석 → 삭제의 전체 플로우를 관리합니다.
    """
    
    def __init__(self):
        """초기화"""
        load_dotenv()
        
        # OpenAI 클라이언트
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        
        # 세션 매니저
        self.session_manager = SessionManager()
        
        # 영구 RAG (SCAMPER, Mind Mapping, Starbursting) ChromaDB 초기화
        current_file = Path(__file__).resolve()
        module_dir = current_file.parent
        persist_directory = str(module_dir / "data" / "chroma")
        
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        try:
            # 컬렉션 목록 확인 후 로드
            print(f"🔍 ChromaDB 경로: {persist_directory}")
            print("🔍 list_collections() 호출 중...")
            collections = self.chroma_client.list_collections()
            print(f"🔍 컬렉션 목록: {collections}")
            collection_names = [c.name for c in collections]
            print(f"🔍 컬렉션 이름들: {collection_names}")
            
            if "brainstorming_techniques" in collection_names:
                print("🔍 get_collection() 호출 중...")
                self.permanent_collection = self.chroma_client.get_collection(
                    name="brainstorming_techniques"
                )
                print(f"✅ 영구 RAG 컬렉션 로드 완료 ({self.permanent_collection.count()}개 문서)")
            else:
                print("⚠️  영구 RAG 컬렉션이 없습니다.")
                print("   chroma_loader.py를 먼저 실행해주세요.")
                self.permanent_collection = None
        except Exception as e:
            import traceback
            print(f"⚠️  영구 RAG 컬렉션 로드 실패: {e}")
            print("   상세 에러:")
            traceback.print_exc()
            print("   chroma_loader.py를 먼저 실행해주세요.")
            self.permanent_collection = None
        
        # 현재 세션 정보
        self.current_session_id = None
        self.ephemeral_rag = None
        
        print("✅ 아이디어 생성 도구 초기화 완료")
        
        # 트렌드 검색기 초기화 (optional)
        try:
            self.trend_searcher = NaverNewsSearcher()
            print("✅ 네이버 트렌드 검색 초기화 완료")
        except Exception as e:
            print(f"⚠️  트렌드 검색 초기화 실패 (기능 비활성화): {e}")
            self.trend_searcher = None
        
        # 덕덕고 검색기 초기화
        try:
            self.duckduckgo_searcher = DuckDuckGoSearcher()
            print("✅ DuckDuckGo 트렌드 검색 초기화 완료")
        except Exception as e:
            print(f"⚠️  DuckDuckGo 초기화 실패 (기능 비활성화): {e}")
            self.duckduckgo_searcher = None
        
        # 네이버 데이터랩 검색기 초기화
        try:
            self.datalab_searcher = NaverDataLabSearcher()
            print("✅ 네이버 데이터랩 검색 초기화 완료")
        except Exception as e:
            print(f"⚠️  네이버 데이터랩 초기화 실패 (기능 비활성화): {e}")
            self.datalab_searcher = None
    
    def start_new_session(self) -> str:
        self.current_session_id = self.session_manager.create_session()
        session = self.session_manager.get_session(self.current_session_id)
        self.ephemeral_rag = EphemeralRAG(session_id=self.current_session_id)
        
        print(f"\n{'='*60}")
        print(f"🎨 새로운 아이디어 생성 세션 시작")
        print(f"   세션 ID: {self.current_session_id}")
        print(f"{'='*60}\n")
        
        return self.current_session_id
    
    def q1_ask_purpose(self) -> str:
        print("📋 Q1: 어디에 쓸 아이디어가 필요하신가요?")
        print("    (예: 모바일 앱, 마케팅 캠페인, 신제품 기획 등)")
        
        purpose = input("\n💭 입력: ").strip()
        self.session_manager.update_session(self.current_session_id, {'q1_purpose': purpose})
        
        print(f"\n✅ 목적이 설정되었습니다: {purpose}\n")
        return purpose
    
    def fetch_trend_keywords(self, purpose: str) -> List[str]:
        all_keywords = []
        
        if self.trend_searcher:
            print("🔍 네이버 트렌드 키워드 검색 중...")
            try:
                naver_keywords = asyncio.run(self.trend_searcher.extract_trend_keywords(purpose, num_articles=5))
                if naver_keywords:
                    print(f"   ✅ 네이버: {len(naver_keywords)}개 발견")
                    all_keywords.extend(naver_keywords)
            except Exception as e:
                print(f"   ⚠️  네이버 검색 실패: {e}")
        
        if self.duckduckgo_searcher:
            print("🔍 DuckDuckGo 글로벌 트렌드 검색 중...")
            try:
                ddg_keywords = asyncio.run(self.duckduckgo_searcher.extract_trend_keywords(purpose, num_articles=5))
                if ddg_keywords:
                    print(f"   ✅ DuckDuckGo: {len(ddg_keywords)}개 발견")
                    all_keywords.extend(ddg_keywords)
            except Exception as e:
                print(f"   ⚠️  DuckDuckGo 검색 실패: {e}")
        
        if self.datalab_searcher:
            print("🔍 네이버 데이터랩 트렌드 검색 중...")
            try:
                datalab_keywords = asyncio.run(self.datalab_searcher.extract_trend_keywords(purpose))
                if datalab_keywords:
                    print(f"   ✅ 네이버 데이터랩: {len(datalab_keywords)}개 발견")
                    all_keywords.extend(datalab_keywords)
            except Exception as e:
                print(f"   ⚠️  네이버 데이터랩 검색 실패: {e}")
        
        unique_keywords = list(dict.fromkeys(all_keywords))
        
        if unique_keywords:
            print(f"\n✅ 총 트렌드 키워드 {len(unique_keywords)}개:")
            for kw in unique_keywords:
                print(f"   - {kw}")
        else:
            print("⚠️  트렌드 키워드를 찾지 못했습니다.")
        
        return unique_keywords
    
    def q2_generate_warmup(self, purpose: str) -> List[str]:
        print("🤔 Q2: 브레인스토밍 워밍업")
        print("    LLM이 워밍업 질문을 생성하고 있습니다...\n")
        
        prompt = f"""사용자가 "{purpose}"에 대한 아이디어를 생성하려고 합니다.

**목표**: 사용자의 직군/상황에 맞는 구체적인 워밍업 질문 2-3개 생성

1. 먼저 목적을 보고 직군을 추론하세요 (유튜버, 회사원, 소상공인, 개발자, 학생 등)
2. 해당 직군이 고민할 법한 구체적 질문을 만드세요

각 질문은 번호를 붙여 한 줄로 작성해주세요."""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 유능한 기획자입니다. 사용자의 직군에 맞는 구체적이고 실용적인 질문을 던집니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=400
            )
            
            warmup_text = response.choices[0].message.content.strip()
            warmup_questions = []
            for line in warmup_text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    cleaned = line.lstrip('0123456789.-•) ').strip()
                    if cleaned:
                        warmup_questions.append(cleaned)
            
            self.session_manager.update_session(self.current_session_id, {'q2_warmup': warmup_questions})
            
            print("💡 워밍업 질문:\n")
            for i, question in enumerate(warmup_questions, 1):
                print(f"   {i}. {question}")
            
            return warmup_questions
            
        except Exception as e:
            print(f"❌ 워밍업 질문 생성 실패: {e}")
            return []
    
    def q2_wait_for_confirmation(self) -> bool:
        import time as time_module
        time_module.sleep(0.1)
        try:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except:
            pass
        
        print("\n")
        response = input("준비가 되셨다면 '네'를 입력해주세요: ").strip()
        
        if response == "네":
            print("✅ Q3로 넘어갑니다!\n")
            return True
        else:
            print("⚠️  '네'를 입력해야 다음 단계로 진행됩니다.")
            return False
    
    def q3_free_association(self, time_limit: int = 30, min_items: int = 10, max_items: int = 20) -> List[str]:
        print("🚀 Q3: 자유연상")
        print(f"    지금부터 {time_limit}초 동안 떠오르는 무엇이든 자유롭게 많이 적어주세요.")
        print(f"    각 항목은 엔터로 구분하세요. (최소 {min_items}개, 최대 {max_items}개)")
        print(f"\n⏱️  입력 시작!\n")
        
        associations = []
        start_time = time.time()
        
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(time_limit)
            
            while len(associations) < max_items:
                try:
                    elapsed = int(time.time() - start_time)
                    remaining = time_limit - elapsed
                    
                    if remaining <= 0:
                        break
                    
                    item = input(f"[{remaining}초 남음, {len(associations)}/{max_items}개] 💭 ").strip()
                    if item:
                        associations.append(item)
                        if len(associations) >= max_items:
                            print(f"\n✅ 최대 {max_items}개 입력 완료! 자동 종료됩니다.")
                            break
                        
                except TimeoutException:
                    print("\n⏰ 시간 종료!")
                    break
                except EOFError:
                    break
            
            signal.alarm(0)
            
        except Exception as e:
            print(f"\n⚠️  입력 중 오류 발생: {e}")
            signal.alarm(0)
        
        import time as time_module
        time_module.sleep(0.1)
        try:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except:
            pass
        
        print(f"\n✅ {len(associations)}개 항목 입력 완료!")
        
        if len(associations) < min_items:
            print(f"\n⚠️  최소 {min_items}개 이상 입력해주세요! (현재: {len(associations)}개)")
            print(f"    {min_items - len(associations)}개 더 필요합니다.\n")
            
            remaining_needed = min_items - len(associations)
            remaining_allowed = max_items - len(associations)
            print(f"🔄 다시 {time_limit}초 동안 추가 입력해주세요! (최소 {remaining_needed}개 더, 최대 {remaining_allowed}개까지)\n")
            additional = self.q3_free_association_retry(time_limit, remaining_needed, remaining_allowed)
            associations.extend(additional)
        
        self.session_manager.update_session(self.current_session_id, {'q3_associations': associations})
        self.ephemeral_rag.add_associations(associations)
        
        print(f"\n✅ 총 {len(associations)}개 항목이 저장되었습니다.\n")
        return associations
    
    def q3_free_association_retry(self, time_limit: int, needed: int, max_allowed: int) -> List[str]:
        associations = []
        start_time = time.time()
        
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(time_limit)
            
            while len(associations) < max_allowed:
                try:
                    elapsed = int(time.time() - start_time)
                    remaining = time_limit - elapsed
                    
                    if remaining <= 0:
                        break
                    
                    if len(associations) < needed:
                        status = f"{needed - len(associations)}개 더 필요"
                    else:
                        status = f"충분함, 최대 {max_allowed - len(associations)}개 더 가능"
                    
                    item = input(f"[{remaining}초 남음, {status}] 💭 ").strip()
                    if item:
                        associations.append(item)
                        if len(associations) >= max_allowed:
                            print(f"\n✅ 최대 개수 도달! 자동 종료됩니다.")
                            break
                        
                except TimeoutException:
                    print("\n⏰ 시간 종료!")
                    break
                except EOFError:
                    break
            
            signal.alarm(0)
            
        except Exception as e:
            print(f"\n⚠️  입력 중 오류 발생: {e}")
            signal.alarm(0)
        
        import time as time_module
        time_module.sleep(0.1)
        try:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except:
            pass
        
        return associations
    
    def _search_permanent_rag(self, query: str, n_results: int = 5) -> List[Dict]:
        if not self.permanent_collection:
            return []
        
        try:
            query_embedding = self.ephemeral_rag.embed_text(query)
            results = self.permanent_collection.query(query_embeddings=[query_embedding], n_results=n_results)
            
            techniques = []
            if results['documents'] and len(results['documents'][0]) > 0:
                for i in range(len(results['documents'][0])):
                    techniques.append({
                        'title': results['metadatas'][0][i].get('title', 'N/A'),
                        'content': results['documents'][0][i],
                        'chunk_id': results['metadatas'][0][i].get('chunk_id', 'N/A'),
                        'similarity': 1 - results['distances'][0][i] if results['distances'] else 0
                    })
            
            return techniques
            
        except Exception as e:
            print(f"⚠️  영구 RAG 검색 실패: {e}")
            return []
    
    def generate_ideas(self, purpose: str, keywords: List[Dict], top_k_techniques: int = 3, trend_keywords: List[str] = None) -> List[Dict]:
        print("🎨 아이디어 생성 중...\n")
        
        techniques_results = self._search_permanent_rag(query=purpose, n_results=top_k_techniques)
        keyword_str = ", ".join([kw['keyword'] for kw in keywords[:7]])
        techniques_str = "\n\n".join([f"[기법 {i+1}] {t['title']}\n{t['content'][:500]}..." for i, t in enumerate(techniques_results)])
        
        domain_hint = get_domain_hint(purpose)
        formatted_hint = format_hint_for_prompt(domain_hint)
        
        prompt = f"""사용자가 "{purpose}"에 대한 아이디어를 원합니다.

【🔴 핵심: 사용자 브레인스토밍 키워드 (비중 80%)】
{keyword_str}

【🔵 참고: 최신 트렌드 키워드 (비중 20%)】
{", ".join(trend_keywords) if trend_keywords else "없음"}

【적용 가능한 브레인스토밍 기법】
{techniques_str}
{formatted_hint}

---
**🚨 필수 규칙**
1. 반드시 3개 아이디어 생성
2. 비중 준수: 사용자 키워드 80% + 트렌드 20%
3. 할루시네이션 금지 (통계, 비용, 시장규모 지어내기 금지)
4. 현실적 실행 가능: 며칠~몇 주 내 시작 가능한 것만
5. 자연스럽고 대화하듯 작성 (딱딱한 보고서 형식 X)

**출력 형식**:
---
아이디어 제목: [제목]
주제: [어떤 문제/니즈가 있는지 자연스러운 문장으로]
실행 방향: [무엇을 어떻게 할지 대화하듯 설명]
기대효과: [이렇게 하면 어떤 결과가 기대되는지]
고민사항: [실행 전 검토할 점들을 질문 형태로. 예: "~는 충분할까?", "~를 어떻게 확보할까?"]
적용된 기법: [기법명]
---"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 현실적인 기획자입니다. 허구의 통계나 비용을 절대 지어내지 않으며, 사용자가 가진 자원과 역량으로 빠르게 시작 가능한 아이디어를 제안합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            ideas_text = response.choices[0].message.content.strip()
            ideas = self._parse_ideas(ideas_text)
            
            self.session_manager.update_session(self.current_session_id, {'ideas': ideas})
            
            print(f"✅ {len(ideas)}개의 아이디어가 생성되었습니다!\n")
            for i, idea in enumerate(ideas, 1):
                print(f"{'='*60}")
                print(f"💡 아이디어 {i}: {idea.get('title', '제목 없음')}")
                print(f"{'='*60}")
                if idea.get('subject'):
                    print(f"\n📌 주제\n{idea.get('subject')}")
                if idea.get('direction'):
                    print(f"\n🎯 실행 방향\n{idea.get('direction')}")
                if idea.get('expected_effect'):
                    print(f"\n✨ 기대효과\n{idea.get('expected_effect')}")
                if idea.get('concerns'):
                    print(f"\n🤔 고민사항\n{idea.get('concerns')}")
                print(f"\n🔧 적용 기법: {idea.get('technique', '기법 없음')}\n")
            
            return ideas
            
        except Exception as e:
            print(f"❌ 아이디어 생성 실패: {e}")
            return []
    
    def _parse_ideas(self, ideas_text: str) -> List[Dict]:
        ideas = []
        current_idea = {}
        current_field = None
        
        for line in ideas_text.split('\n'):
            line = line.strip()
            
            if line.startswith('---'):
                if current_idea and current_idea.get('title'):
                    ideas.append(current_idea)
                current_idea = {}
                current_field = None
            elif line.startswith('아이디어 제목:') or line.startswith('제목:'):
                current_idea['title'] = line.split(':', 1)[1].strip()
                current_field = None
            elif line.startswith('주제:'):
                current_idea['subject'] = line.split(':', 1)[1].strip()
                current_field = 'subject'
            elif line.startswith('실행 방향:'):
                current_idea['direction'] = line.split(':', 1)[1].strip()
                current_field = 'direction'
            elif line.startswith('기대효과:') or line.startswith('기대 효과:'):
                current_idea['expected_effect'] = line.split(':', 1)[1].strip()
                current_field = 'expected_effect'
            elif line.startswith('고민사항:') or line.startswith('확인 필요 사항:') or line.startswith('확인 필요:'):
                current_idea['concerns'] = line.split(':', 1)[1].strip()
                current_field = 'concerns'
            elif line.startswith('적용된 기법:') or line.startswith('기법:'):
                current_idea['technique'] = line.split(':', 1)[1].strip()
                current_field = None
            elif current_field and line:
                if current_field in current_idea:
                    current_idea[current_field] += ' ' + line
                else:
                    current_idea[current_field] = line
        
        if current_idea and current_idea.get('title'):
            ideas.append(current_idea)
        
        return ideas
    
    def analyze_ideas(self, ideas: List[Dict]) -> List[Dict]:
        print("\n📊 아이디어 분석 중...\n")
        
        for i, idea in enumerate(ideas, 1):
            print(f"{'='*60}")
            print(f"📈 아이디어 {i} 분석: {idea.get('title', '제목 없음')}")
            print(f"{'='*60}\n")
            
            analysis = self._perform_swot_analysis(idea)
            idea['analysis'] = analysis
            idea['analysis_type'] = 'SWOT'
            
            print(f"강점 (Strengths):\n{analysis.get('strengths', 'N/A')}\n")
            print(f"약점 (Weaknesses):\n{analysis.get('weaknesses', 'N/A')}\n")
            print(f"기회 (Opportunities):\n{analysis.get('opportunities', 'N/A')}\n")
            print(f"위협 (Threats):\n{analysis.get('threats', 'N/A')}\n")
        
        self.session_manager.update_session(self.current_session_id, {'ideas': ideas})
        
        print(f"{'='*60}\n")
        print("✅ 모든 아이디어 분석 완료!\n")
        
        return ideas
    
    def _perform_swot_analysis(self, idea: Dict) -> Dict:
        # description 생성
        desc = idea.get('description', '')
        if not desc:
            parts = []
            if idea.get('subject'):
                parts.append(idea['subject'])
            if idea.get('direction'):
                parts.append(idea['direction'])
            desc = ' '.join(parts)
        
        prompt = f"""다음 아이디어에 대해 SWOT 분석을 수행해주세요:

아이디어 제목: {idea.get('title', '제목 없음')}
설명: {desc}

**필수 형식** (반드시 4가지 모두 작성):

강점 (Strengths):
- [핵심 장점 1줄]

약점 (Weaknesses):
- [솔직한 단점 1줄]

기회 (Opportunities):
- [현실적 기회 1줄]

위협 (Threats):
- [구체적 위협 1줄]"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 현실적인 기획자입니다. SWOT 분석은 짧고 간결하게 작성합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=500
            )
            
            analysis_text = response.choices[0].message.content.strip()
            
            swot = {'strengths': '', 'weaknesses': '', 'opportunities': '', 'threats': ''}
            current_section = None
            
            for line in analysis_text.split('\n'):
                line = line.strip()
                
                if '강점' in line or 'Strengths' in line.lower():
                    current_section = 'strengths'
                    if ':' in line:
                        content = line.split(':', 1)[1].strip()
                        if content:
                            swot['strengths'] = content
                elif '약점' in line or 'Weaknesses' in line.lower():
                    current_section = 'weaknesses'
                    if ':' in line:
                        content = line.split(':', 1)[1].strip()
                        if content:
                            swot['weaknesses'] = content
                elif '기회' in line or 'Opportunities' in line.lower():
                    current_section = 'opportunities'
                    if ':' in line:
                        content = line.split(':', 1)[1].strip()
                        if content:
                            swot['opportunities'] = content
                elif '위협' in line or 'Threats' in line.lower():
                    current_section = 'threats'
                    if ':' in line:
                        content = line.split(':', 1)[1].strip()
                        if content:
                            swot['threats'] = content
                elif current_section and line and line not in ['', '-', '•', '*']:
                    cleaned_line = line.lstrip('-•*').strip()
                    if cleaned_line:
                        if swot[current_section]:
                            swot[current_section] += ' ' + cleaned_line
                        else:
                            swot[current_section] = cleaned_line
            
            for key in swot:
                if not swot[key]:
                    swot[key] = '(분석 데이터 없음)'
            
            return swot
            
        except Exception as e:
            print(f"⚠️  SWOT 분석 실패: {e}")
            return {'strengths': 'N/A', 'weaknesses': 'N/A', 'opportunities': 'N/A', 'threats': 'N/A'}
    
    def confirm_deletion(self) -> bool:
        import time as time_module
        time_module.sleep(0.2)
        try:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except:
            pass
        
        print("\n" + "="*60)
        print("🗑️  데이터 삭제")
        print("="*60)
        print("\n이번 세션의 모든 데이터를 삭제하시겠습니까?")
        print("(Q1 목적, Q2 워밍업, Q3 연상, 생성된 아이디어, 임시 벡터 DB)\n")
        
        response = input("삭제하려면 '네'를 입력해주세요: ").strip()
        return response == "네"
    
    def delete_session_data(self):
        if not self.current_session_id:
            print("⚠️  삭제할 세션이 없습니다.")
            return
        
        print("\n🗑️  데이터 삭제 중...")
        
        if self.ephemeral_rag:
            self.ephemeral_rag.delete_session_data()
        
        self.session_manager.delete_session(self.current_session_id)
        
        print("✅ 모든 데이터가 삭제되었습니다.")
        print("   아이디어 오염 및 유출이 방지되었습니다.\n")
        
        self.current_session_id = None
        self.ephemeral_rag = None
    
    # ============================================================
    # API용 메서드 (엔드포인트에서 호출)
    # ============================================================
    
    async def generate_ideas_for_api(self, session_id: str, purpose: str, associations: List[str]) -> List[Dict]:
        print(f"[API] 아이디어 생성 시작 - 세션: {session_id}")
        
        ephemeral_rag = EphemeralRAG(session_id=session_id)
        
        keywords_data = ephemeral_rag.extract_keywords_by_similarity(purpose=purpose, top_k=7)
        extracted_keywords = [kw['keyword'] for kw in keywords_data]
        print(f"[API] 추출된 키워드: {extracted_keywords}")
        
        trend_keywords = await self._fetch_trend_keywords_async(purpose)
        print(f"[API] 트렌드 키워드 (필터링 전): {len(trend_keywords)}개")
        
        if trend_keywords:
            trend_keywords = ephemeral_rag.filter_trend_keywords(trend_keywords, top_k=10)
            print(f"[API] 트렌드 키워드 (필터링 후): {trend_keywords}")
        
        techniques_results = self._search_permanent_rag_for_api(query=purpose, n_results=3, ephemeral_rag=ephemeral_rag)
        
        ideas = self._generate_ideas_with_prompt(
            purpose=purpose,
            keywords=extracted_keywords,
            techniques=techniques_results,
            trend_keywords=trend_keywords
        )
        
        for idea in ideas:
            swot = self._perform_swot_analysis(idea)
            swot_text = f"""

📊 분석 결과:
• 강점: {swot.get('strengths', 'N/A')}
• 약점: {swot.get('weaknesses', 'N/A')}
• 기회: {swot.get('opportunities', 'N/A')}
• 위협: {swot.get('threats', 'N/A')}"""
            idea['analysis'] = swot_text
        
        print(f"[API] 아이디어 생성 완료: {len(ideas)}개")
        return ideas
    
    async def _fetch_trend_keywords_async(self, purpose: str) -> List[str]:
        all_keywords = []
        
        if self.trend_searcher:
            try:
                naver_keywords = await self.trend_searcher.extract_trend_keywords(purpose, num_articles=5)
                if naver_keywords:
                    all_keywords.extend(naver_keywords)
                    print(f"[API] 네이버 뉴스: {len(naver_keywords)}개")
            except Exception as e:
                print(f"[API] 네이버 뉴스 검색 실패: {e}")
        
        if self.duckduckgo_searcher:
            try:
                ddg_keywords = await self.duckduckgo_searcher.extract_trend_keywords(purpose, num_articles=5)
                if ddg_keywords:
                    all_keywords.extend(ddg_keywords)
                    print(f"[API] DuckDuckGo: {len(ddg_keywords)}개")
            except Exception as e:
                print(f"[API] DuckDuckGo 검색 실패: {e}")
        
        if self.datalab_searcher:
            try:
                datalab_keywords = await self.datalab_searcher.extract_trend_keywords(purpose)
                if datalab_keywords:
                    all_keywords.extend(datalab_keywords)
                    print(f"[API] 네이버 데이터랩: {len(datalab_keywords)}개")
            except Exception as e:
                print(f"[API] 네이버 데이터랩 검색 실패: {e}")
        
        return list(dict.fromkeys(all_keywords))
    
    def _search_permanent_rag_for_api(self, query: str, n_results: int = 3, ephemeral_rag: EphemeralRAG = None) -> List[Dict]:
        if not self.permanent_collection:
            return []
        
        try:
            if ephemeral_rag:
                query_embedding = ephemeral_rag.embed_text(query)
            else:
                response = self.openai_client.embeddings.create(model=self.embedding_model, input=query)
                query_embedding = response.data[0].embedding
            
            results = self.permanent_collection.query(query_embeddings=[query_embedding], n_results=n_results)
            
            techniques = []
            if results['documents'] and len(results['documents'][0]) > 0:
                for i in range(len(results['documents'][0])):
                    techniques.append({
                        'title': results['metadatas'][0][i].get('title', 'N/A'),
                        'content': results['documents'][0][i],
                    })
            return techniques
        except Exception as e:
            print(f"[API] 영구 RAG 검색 실패: {e}")
            return []
    
    def _generate_ideas_with_prompt(self, purpose: str, keywords: List[str], techniques: List[Dict], trend_keywords: List[str] = None) -> List[Dict]:
        keyword_str = ", ".join(keywords[:7])
        techniques_str = "\n\n".join([f"[기법 {i+1}] {t['title']}\n{t['content'][:500]}..." for i, t in enumerate(techniques)]) if techniques else "(기법 없음)"
        
        domain_hint = get_domain_hint(purpose)
        formatted_hint = format_hint_for_prompt(domain_hint)
        
        prompt = f"""사용자가 "{purpose}"에 대한 아이디어를 원합니다.

【🔴 핵심: 사용자 브레인스토밍 키워드 (비중 80%)】
{keyword_str}

【🔵 참고: 최신 트렌드 키워드 (비중 20%)】
{", ".join(trend_keywords) if trend_keywords else "없음"}

【적용 가능한 브레인스토밍 기법】
{techniques_str}
{formatted_hint}

---
**🚨 필수 규칙**
1. 반드시 3개 아이디어 생성
2. 비중 준수: 사용자 키워드 80% + 트렌드 20%
3. 할루시네이션 금지 (통계, 비용, 시장규모 지어내기 금지)
4. 현실적 실행 가능: 며칠~몇 주 내 시작 가능한 것만
5. 자연스럽고 대화하듯 작성 (딱딱한 보고서 형식 X)

**출력 형식**:
---
아이디어 제목: [제목]
주제: [어떤 문제/니즈가 있는지 자연스러운 문장으로]
실행 방향: [무엇을 어떻게 할지 대화하듯 설명]
기대효과: [이렇게 하면 어떤 결과가 기대되는지]
고민사항: [실행 전 검토할 점들을 질문 형태로. 예: "~는 충분할까?", "~를 어떻게 확보할까?"]
적용된 기법: [기법명]
---"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 현실적인 기획자입니다. 허구의 통계나 비용을 절대 지어내지 않습니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            ideas_text = response.choices[0].message.content.strip()
            return self._parse_ideas_for_api(ideas_text)
        except Exception as e:
            print(f"[API] 아이디어 생성 실패: {e}")
            return []
    
    def _parse_ideas_for_api(self, ideas_text: str) -> List[Dict]:
        ideas = []
        current_idea = {}
        current_field = None
        
        for line in ideas_text.split('\n'):
            line = line.strip()
            
            if line.startswith('---'):
                if current_idea and current_idea.get('title'):
                    # description 생성 (주제 + 실행방향 + 기대효과 + 고민사항)
                    desc_parts = []
                    if current_idea.get('subject'):
                        desc_parts.append(f"📌 주제\n{current_idea['subject']}")
                    if current_idea.get('direction'):
                        desc_parts.append(f"🎯 실행 방향\n{current_idea['direction']}")
                    if current_idea.get('expected_effect'):
                        desc_parts.append(f"✨ 기대효과\n{current_idea['expected_effect']}")
                    if current_idea.get('concerns'):
                        desc_parts.append(f"🤔 고민사항\n{current_idea['concerns']}")
                    if current_idea.get('technique'):
                        desc_parts.append(f"🔧 적용 기법: {current_idea['technique']}")
                    current_idea['description'] = '\n\n'.join(desc_parts)
                    ideas.append(current_idea)
                current_idea = {}
                current_field = None
            elif line.startswith('아이디어 제목:') or line.startswith('제목:'):
                current_idea['title'] = line.split(':', 1)[1].strip()
            elif line.startswith('주제:'):
                current_idea['subject'] = line.split(':', 1)[1].strip()
                current_field = 'subject'
            elif line.startswith('실행 방향:'):
                current_idea['direction'] = line.split(':', 1)[1].strip()
                current_field = 'direction'
            elif line.startswith('기대효과:') or line.startswith('기대 효과:'):
                current_idea['expected_effect'] = line.split(':', 1)[1].strip()
                current_field = 'expected_effect'
            elif line.startswith('고민사항:') or line.startswith('확인 필요 사항:') or line.startswith('확인 필요:'):
                current_idea['concerns'] = line.split(':', 1)[1].strip()
                current_field = 'concerns'
            elif line.startswith('적용된 기법:') or line.startswith('기법:'):
                current_idea['technique'] = line.split(':', 1)[1].strip()
                current_field = None
            elif current_field and line:
                if current_field in current_idea:
                    current_idea[current_field] += ' ' + line
                else:
                    current_idea[current_field] = line
        
        # 마지막 아이디어
        if current_idea and current_idea.get('title'):
            desc_parts = []
            if current_idea.get('subject'):
                desc_parts.append(f"📌 주제\n{current_idea['subject']}")
            if current_idea.get('direction'):
                desc_parts.append(f"🎯 실행 방향\n{current_idea['direction']}")
            if current_idea.get('expected_effect'):
                desc_parts.append(f"✨ 기대효과\n{current_idea['expected_effect']}")
            if current_idea.get('concerns'):
                desc_parts.append(f"🤔 고민사항\n{current_idea['concerns']}")
            if current_idea.get('technique'):
                desc_parts.append(f"🔧 적용 기법: {current_idea['technique']}")
            current_idea['description'] = '\n\n'.join(desc_parts)
            ideas.append(current_idea)
        
        return ideas
    
    def run(self):
        try:
            self.start_new_session()
            purpose = self.q1_ask_purpose()
            trend_keywords = self.fetch_trend_keywords(purpose)
            warmup_questions = self.q2_generate_warmup(purpose)
            
            while not self.q2_wait_for_confirmation():
                pass
            
            associations = self.q3_free_association(time_limit=30, min_items=10, max_items=20)
            
            print("\n🔍 Q1과 Q3 간 유사도 기반 키워드 추출 중...\n")
            keywords = self.ephemeral_rag.extract_keywords_by_similarity(purpose, top_k=7)
            
            if trend_keywords:
                print("\n🔍 트렌드 키워드를 사용자 입력 기준으로 필터링 중...")
                trend_keywords = self.ephemeral_rag.filter_trend_keywords(trend_keywords, top_k=10)
            
            ideas = self.generate_ideas(purpose, keywords, top_k_techniques=3, trend_keywords=trend_keywords)
            
            if not ideas:
                print("⚠️  아이디어 생성에 실패했습니다.")
                return
            
            ideas = self.analyze_ideas(ideas)
            
            if self.confirm_deletion():
                self.delete_session_data()
            else:
                print("\n✅ 데이터가 유지됩니다.")
                print(f"   세션 ID: {self.current_session_id}")
                print("   나중에 /delete 명령으로 삭제할 수 있습니다.\n")
            
            print("\n" + "="*60)
            print("🎉 아이디어 생성 완료!")
            print("="*60)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  사용자가 중단했습니다.")
            if self.confirm_deletion():
                self.delete_session_data()
        
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    generator = IdeaGenerator()
    generator.run()
