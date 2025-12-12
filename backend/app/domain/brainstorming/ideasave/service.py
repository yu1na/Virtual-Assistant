"""
브레인스토밍 아이디어 저장 서비스
"""
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.domain.brainstorming.ideasave.repository import BrainstormingRepository
from app.domain.brainstorming.ideasave.schemas import IdeaCreate
from app.domain.brainstorming.ideasave.models import BrainstormingIdea


class IdeaSaveService:
    """브레인스토밍 아이디어 저장/조회/삭제 서비스"""
    
    def save_idea(self, db: Session, user_id: int, idea_data: IdeaCreate) -> BrainstormingIdea:
        """
        브레인스토밍 아이디어 저장
        
        Args:
            db: DB 세션
            user_id: 사용자 ID
            idea_data: 아이디어 데이터
            
        Returns:
            BrainstormingIdea: 저장된 아이디어
        """
        repository = BrainstormingRepository(db)
        return repository.create(user_id, idea_data)
    
    def get_user_ideas(
        self, 
        db: Session, 
        user_id: int, 
        limit: int = 100, 
        offset: int = 0
    ) -> Dict:
        """
        사용자의 아이디어 목록 조회
        
        Args:
            db: DB 세션
            user_id: 사용자 ID
            limit: 최대 개수
            offset: 시작 위치
            
        Returns:
            Dict: {"total": int, "ideas": List[BrainstormingIdea]}
        """
        repository = BrainstormingRepository(db)
        ideas = repository.get_by_user(user_id, limit, offset)
        total = repository.count_by_user(user_id)
        
        return {
            "total": total,
            "ideas": ideas
        }
    
    def get_idea_by_id(self, db: Session, idea_id: int, user_id: int) -> Optional[BrainstormingIdea]:
        """
        아이디어 상세 조회 (본인 확인 포함)
        
        Args:
            db: DB 세션
            idea_id: 아이디어 ID
            user_id: 사용자 ID
            
        Returns:
            Optional[BrainstormingIdea]: 아이디어 또는 None
        """
        repository = BrainstormingRepository(db)
        idea = repository.get_by_id(idea_id)
        
        # 본인 확인
        if idea and idea.user_id != user_id:
            return None
        
        return idea
    
    def delete_idea(self, db: Session, idea_id: int, user_id: int) -> bool:
        """
        아이디어 삭제 (본인 확인 포함)
        
        Args:
            db: DB 세션
            idea_id: 아이디어 ID
            user_id: 사용자 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        repository = BrainstormingRepository(db)
        
        # 본인 확인
        if not repository.is_owner(idea_id, user_id):
            return False
        
        return repository.delete(idea_id)
