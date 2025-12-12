"""
브레인스토밍 청크 임베딩 모듈

이 모듈은 파싱된 청크 데이터를 OpenAI API를 통해 임베딩하고
벡터와 함께 저장합니다.
"""
import json
from pathlib import Path
from typing import List, Dict
from openai import OpenAI
from app.core.config import settings


class ChunkEmbedder:
    """청크를 임베딩하는 클래스"""
    
    def __init__(self):
        # OpenAI 클라이언트 초기화
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        self.embedding_dimension = settings.EMBEDDING_DIMENSION
        
        # 디렉토리 경로 설정
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.embeddings_dir = self.data_dir / "embeddings"
        
    def embed_text(self, text: str) -> List[float]:
        """
        텍스트를 임베딩 벡터로 변환
        
        Args:
            text: 임베딩할 텍스트
            
        Returns:
            임베딩 벡터 (길이 3072의 float 리스트)
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                encoding_format="float"
            )
            
            # 임베딩 벡터 추출
            embedding = response.data[0].embedding
            
            return embedding
            
        except Exception as e:
            print(f"❌ 임베딩 생성 실패: {e}")
            raise
    
    def load_parsed_chunks(self, filename: str = "parsed_chunks.json") -> List[Dict]:
        """
        파싱된 청크 JSON 파일 로드
        
        Args:
            filename: 로드할 파일명
            
        Returns:
            청크 리스트
        """
        file_path = self.embeddings_dir / filename
        
        with open(file_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        return chunks
    
    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        모든 청크를 임베딩하여 embedding 필드 추가
        
        Args:
            chunks: 파싱된 청크 리스트
            
        Returns:
            임베딩이 추가된 청크 리스트
        """
        total = len(chunks)
        embedded_chunks = []
        
        for idx, chunk in enumerate(chunks, 1):
            chunk_id = chunk['chunk_id']
            title = chunk['title']
            content = chunk['content']
            
            print(f"⏳ [{idx}/{total}] 청크 {chunk_id} 임베딩 중: {title[:30]}...")
            
            try:
                # 임베딩 생성 (content를 사용)
                embedding = self.embed_text(content)
                
                # 청크에 임베딩 추가
                chunk['embedding'] = embedding
                chunk['metadata']['embedding_model'] = self.embedding_model
                chunk['metadata']['embedding_dimension'] = len(embedding)
                
                embedded_chunks.append(chunk)
                
                print(f"   ✅ 완료 (벡터 차원: {len(embedding)})")
                
            except Exception as e:
                print(f"   ❌ 실패: {e}")
                # 실패해도 계속 진행 (임베딩 없이 저장)
                embedded_chunks.append(chunk)
        
        return embedded_chunks
    
    def save_embedded_chunks(self, chunks: List[Dict], output_filename: str = "embedded_chunks.json"):
        """
        임베딩된 청크를 JSON 파일로 저장
        
        Args:
            chunks: 임베딩된 청크 리스트
            output_filename: 출력 파일명
        """
        output_path = self.embeddings_dir / output_filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 {len(chunks)}개의 임베딩된 청크가 저장되었습니다: {output_path}")
        return output_path
    
    def process(
        self, 
        input_filename: str = "parsed_chunks.json",
        output_filename: str = "embedded_chunks.json"
    ):
        """
        전체 임베딩 프로세스 실행
        
        Args:
            input_filename: 입력 파일명 (파싱된 청크)
            output_filename: 출력 파일명 (임베딩된 청크)
            
        Returns:
            저장된 파일 경로
        """
        print("=" * 60)
        print("🚀 브레인스토밍 청크 임베딩 시작")
        print("=" * 60)
        
        # 1. 파싱된 청크 로드
        print(f"\n📂 파일 로드 중: {input_filename}")
        chunks = self.load_parsed_chunks(input_filename)
        print(f"✅ {len(chunks)}개의 청크를 로드했습니다.")
        
        # 2. 임베딩 생성
        print(f"\n🔮 OpenAI {self.embedding_model} 모델로 임베딩 중...")
        print(f"   (벡터 차원: {self.embedding_dimension})")
        print()
        
        embedded_chunks = self.embed_chunks(chunks)
        
        # 3. 저장
        print(f"\n💾 임베딩된 데이터 저장 중...")
        output_path = self.save_embedded_chunks(embedded_chunks, output_filename)
        
        # 4. 통계
        successful = sum(1 for c in embedded_chunks if 'embedding' in c)
        failed = len(embedded_chunks) - successful
        
        print("\n" + "=" * 60)
        print("📊 임베딩 완료 통계")
        print("=" * 60)
        print(f"✅ 성공: {successful}개")
        print(f"❌ 실패: {failed}개")
        print(f"📁 저장 위치: {output_path}")
        print(f"💰 예상 비용: ~${(successful * 3072 / 1_000_000) * 0.00013:.6f} USD")
        print("   (text-embedding-3-large: $0.00013 / 1M tokens)")
        print("=" * 60)
        
        return output_path


# 테스트 실행용 코드
if __name__ == "__main__":
    embedder = ChunkEmbedder()
    embedder.process()

