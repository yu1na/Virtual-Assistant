"""
임시 RAG (Ephemeral RAG) 모듈 - JSON 기반

세션별 임시 데이터를 JSON 파일로 처리합니다:
1. Q3 자유연상 입력을 임베딩
2. JSON 파일에 저장 (눈으로 확인 가능!)
3. Q1 목적과 Q3 연상 간의 코사인 유사도 기반 키워드 추출
4. 영구 RAG (SCAMPER, Mind Mapping, Starbursting)와 결합하여 아이디어 생성

변경사항 (2024-11-30):
- ChromaDB → JSON 파일 기반으로 변경
- 데이터가 눈에 보이고 디버깅이 쉬워짐
- 세션별로 data/ephemeral/{session_id}/associations.json에 저장
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv
import os
import shutil


class EphemeralRAG:
    """
    세션별 임시 RAG 처리 클래스 (JSON 기반)
    
    각 세션마다 독립적인 JSON 파일을 생성하고,
    Q3 자유연상 데이터를 임베딩하여 저장합니다.
    """
    
    def __init__(self, session_id: str):
        """
        초기화
        
        Args:
            session_id: 세션 ID
        """
        # .env 파일 로드
        load_dotenv()
        
        self.session_id = session_id
        
        # OpenAI 클라이언트 초기화
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        
        # 세션별 디렉토리 경로 설정
        current_file = Path(__file__).resolve()
        module_dir = current_file.parent
        self.ephemeral_dir = module_dir / "data" / "ephemeral" / session_id
        self.json_path = self.ephemeral_dir / "associations.json"
        
        # 디렉토리 생성
        self.ephemeral_dir.mkdir(parents=True, exist_ok=True)
        
        # 데이터 로드 또는 초기화
        self.data = self._load_data()
        
        print(f"✅ Ephemeral RAG 초기화 (JSON 기반)")
        print(f"   📁 저장 경로: {self.json_path}")
    
    def _load_data(self) -> Dict:
        """JSON 파일에서 데이터 로드"""
        if self.json_path.exists():
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "session_id": self.session_id,
            "associations": []  # [{text, embedding}, ...]
        }
    
    def _save_data(self):
        """JSON 파일에 데이터 저장"""
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def embed_text(self, text: str) -> List[float]:
        """
        텍스트를 임베딩 벡터로 변환
        
        Args:
            text: 임베딩할 텍스트
            
        Returns:
            List[float]: 임베딩 벡터
        """
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ 임베딩 실패: {e}")
            raise
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """코사인 유사도 계산"""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def add_associations(self, associations: List[str]) -> bool:
        """
        Q3 자유연상 데이터를 임베딩하여 JSON에 추가
        
        Args:
            associations: 자유연상 단어/문구 리스트
            
        Returns:
            bool: 성공 여부
        """
        try:
            for association in associations:
                # 임베딩 생성
                embedding = self.embed_text(association)
                
                self.data["associations"].append({
                    "text": association,
                    "embedding": embedding
                })
            
            # JSON 파일에 저장
            self._save_data()
            
            print(f"✅ {len(associations)}개의 연상 단어를 JSON에 저장했습니다.")
            print(f"   📄 파일: {self.json_path}")
            return True
            
        except Exception as e:
            print(f"❌ 연상 단어 추가 실패: {e}")
            return False
    
    def extract_keywords_by_similarity(self, purpose: str, top_k: int = 5) -> List[Dict]:
        """
        Q1 목적과 Q3 연상 간의 코사인 유사도를 계산하여 상위 키워드 추출
        
        Args:
            purpose: Q1 목적 (예: "모바일 앱 아이디어")
            top_k: 추출할 상위 키워드 개수
            
        Returns:
            List[Dict]: 상위 키워드 리스트 (각각 keyword, similarity 포함)
        """
        try:
            if not self.data["associations"]:
                print("⚠️ 저장된 연상 단어가 없습니다.")
                return []
            
            # Q1 목적 임베딩
            purpose_embedding = self.embed_text(purpose)
            
            # 모든 연상 단어와 유사도 계산
            similarities = []
            for item in self.data["associations"]:
                similarity = self._cosine_similarity(purpose_embedding, item["embedding"])
                similarities.append({
                    "keyword": item["text"],
                    "similarity": similarity
                })
            
            # 유사도 기준 정렬 후 상위 k개 추출
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            keywords = similarities[:top_k]
            
            print(f"\n✅ Q1과 가장 유사한 상위 {len(keywords)}개 키워드:")
            for i, kw in enumerate(keywords, 1):
                print(f"   {i}. {kw['keyword']} (유사도: {kw['similarity']:.4f})")
            
            return keywords
            
        except Exception as e:
            print(f"❌ 키워드 추출 실패: {e}")
            return []
    
    def search_associations(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        저장된 연상 단어에서 검색
        
        Args:
            query: 검색 쿼리
            n_results: 반환할 결과 개수
            
        Returns:
            List[Dict]: 검색 결과 리스트
        """
        try:
            if not self.data["associations"]:
                return []
            
            query_embedding = self.embed_text(query)
            
            # 모든 연상 단어와 유사도 계산
            results = []
            for item in self.data["associations"]:
                similarity = self._cosine_similarity(query_embedding, item["embedding"])
                results.append({
                    "document": item["text"],
                    "similarity": similarity
                })
            
            # 유사도 기준 정렬 후 상위 n개 반환
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:n_results]
            
        except Exception as e:
            print(f"❌ 검색 실패: {e}")
            return []
    
    def delete_session_data(self) -> bool:
        """
        세션 데이터 삭제 (폴더 전체 삭제)
        
        Returns:
            bool: 성공 여부
        """
        try:
            if self.ephemeral_dir.exists():
                shutil.rmtree(self.ephemeral_dir)
                print(f"✅ 세션 데이터 삭제 완료: {self.ephemeral_dir}")
            return True
        except Exception as e:
            print(f"❌ 세션 데이터 삭제 실패: {e}")
            return False
    
    def get_association_count(self) -> int:
        """
        저장된 연상 단어 개수 조회
        
        Returns:
            int: 항목 개수
        """
        return len(self.data.get("associations", []))
    
    def get_all_associations(self) -> List[str]:
        """
        저장된 모든 연상 단어 텍스트 반환 (임베딩 제외)
        
        Returns:
            List[str]: 연상 단어 리스트
        """
        return [item["text"] for item in self.data.get("associations", [])]
    
    def filter_trend_keywords(self, trend_keywords: List[str], top_k: int = 10) -> List[str]:
        """
        트렌드 키워드를 사용자 Q3 키워드 기준으로 필터링
        
        사용자 키워드와 유사한 트렌드만 선별하여 쏠림 방지
        
        Args:
            trend_keywords: 트렌드 키워드 리스트
            top_k: 선별할 상위 개수
            
        Returns:
            List[str]: 필터링된 트렌드 키워드
        """
        if not self.data["associations"]:
            print("⚠️ 사용자 키워드가 없어 트렌드 필터링 불가")
            return trend_keywords[:top_k]
        
        if not trend_keywords:
            return []
        
        # 1. 사용자 키워드들의 평균 임베딩 계산 (기준점)
        user_embeddings = [item["embedding"] for item in self.data["associations"]]
        avg_user_embedding = np.mean(user_embeddings, axis=0).tolist()
        
        # 2. 각 트렌드 키워드와 사용자 기준점 간 유사도 계산
        trend_scores = []
        for trend_kw in trend_keywords:
            try:
                trend_embedding = self.embed_text(trend_kw)
                similarity = self._cosine_similarity(avg_user_embedding, trend_embedding)
                trend_scores.append({
                    "keyword": trend_kw,
                    "similarity": similarity
                })
            except Exception as e:
                print(f"⚠️ 트렌드 키워드 임베딩 실패: {trend_kw} - {e}")
                continue
        
        # 3. 유사도 기준 정렬 후 상위 k개 선별
        trend_scores.sort(key=lambda x: x["similarity"], reverse=True)
        filtered = [ts["keyword"] for ts in trend_scores[:top_k]]
        
        print(f"\n🔍 트렌드 필터링 결과:")
        print(f"   원본: {len(trend_keywords)}개 → 필터링: {len(filtered)}개")
        for i, ts in enumerate(trend_scores[:top_k], 1):
            print(f"   {i}. {ts['keyword']} (유사도: {ts['similarity']:.4f})")
        
        return filtered


# ============================================================
# 유틸리티 함수들
# ============================================================

def cleanup_old_sessions(max_age_seconds: int = 3600) -> int:
    """
    오래된 세션 데이터 정리
    
    Args:
        max_age_seconds: 이 시간(초)보다 오래된 세션 삭제
        
    Returns:
        int: 삭제된 세션 수
    """
    import time
    
    current_file = Path(__file__).resolve()
    module_dir = current_file.parent
    ephemeral_base = module_dir / "data" / "ephemeral"
    
    if not ephemeral_base.exists():
        return 0
    
    deleted_count = 0
    current_time = time.time()
    
    for session_dir in ephemeral_base.iterdir():
        if session_dir.is_dir():
            # 디렉토리 수정 시간 확인
            dir_mtime = session_dir.stat().st_mtime
            age = current_time - dir_mtime
            
            if age > max_age_seconds:
                try:
                    shutil.rmtree(session_dir)
                    print(f"🧹 오래된 세션 삭제: {session_dir.name}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ 세션 삭제 실패 ({session_dir.name}): {e}")
    
    print(f"✅ 총 {deleted_count}개의 오래된 세션을 청소했습니다.")
    return deleted_count


def get_session_data_path(session_id: str) -> Path:
    """
    세션 데이터 경로 반환
    
    Args:
        session_id: 세션 ID
        
    Returns:
        Path: 세션 데이터 경로
    """
    current_file = Path(__file__).resolve()
    module_dir = current_file.parent
    return module_dir / "data" / "ephemeral" / session_id / "associations.json"


# ============================================================
# 테스트 코드
# ============================================================

if __name__ == "__main__":
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
    
    print("=" * 60)
    print("임시 RAG 테스트 (JSON 기반)")
    print("=" * 60)
    
    # 테스트용 세션 ID
    test_session_id = "test_session_001"
    
    # 1. Ephemeral RAG 초기화
    print("\n[1] Ephemeral RAG 초기화")
    ephemeral_rag = EphemeralRAG(session_id=test_session_id)
    
    # 2. Q1 목적 설정
    print("\n[2] Q1 목적 설정")
    q1_purpose = "건강 관리 모바일 앱 아이디어"
    print(f"    Q1: {q1_purpose}")
    
    # 3. Q3 자유연상 추가
    print("\n[3] Q3 자유연상 추가")
    q3_associations = [
        "운동", "식단", "수면", "스트레칭", "요가",
        "칼로리", "걸음 수", "심박수", "명상", "물 마시기"
    ]
    ephemeral_rag.add_associations(q3_associations)
    print(f"    추가된 연상 단어: {len(q3_associations)}개")
    print(f"    저장된 항목 수: {ephemeral_rag.get_association_count()}개")
    
    # 4. Q1과 Q3 간 유사도 기반 키워드 추출
    print("\n[4] Q1-Q3 유사도 기반 키워드 추출")
    top_keywords = ephemeral_rag.extract_keywords_by_similarity(q1_purpose, top_k=5)
    
    # 5. 특정 쿼리로 검색
    print("\n[5] 특정 쿼리로 검색")
    search_query = "운동과 관련된 기능"
    search_results = ephemeral_rag.search_associations(search_query, n_results=3)
    print(f"    검색 쿼리: {search_query}")
    for i, result in enumerate(search_results, 1):
        print(f"    {i}. {result['document']} (유사도: {result['similarity']:.4f})")
    
    # 6. JSON 파일 확인
    print("\n[6] JSON 파일 확인")
    print(f"    📄 {ephemeral_rag.json_path}")
    print(f"    👀 파일을 직접 열어서 내용을 확인할 수 있습니다!")
    
    # 7. 세션 데이터 삭제
    print("\n[7] 세션 데이터 삭제")
    ephemeral_rag.delete_session_data()
    
    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
