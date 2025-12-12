"""
브레인스토밍 아이디어 Repository
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.domain.brainstorming.ideasave.models import BrainstormingIdea
from app.domain.brainstorming.ideasave.schemas import IdeaCreate


class BrainstormingRepository:
    """브레인스토밍 아이디어 Repository"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_id: int, idea_data: IdeaCreate) -> BrainstormingIdea:
        """
        아이디어 생성
        
        Args:
            user_id: 사용자 ID
            idea_data: 아이디어 데이터
            
        Returns:
            BrainstormingIdea: 생성된 아이디어
        """
        idea = BrainstormingIdea(
            user_id=user_id,
            title=idea_data.title,
            description=idea_data.description
        )
        self.db.add(idea)
        self.db.commit()
        self.db.refresh(idea)
        return idea
    
    def get_by_id(self, idea_id: int) -> Optional[BrainstormingIdea]:
        """
        ID로 아이디어 조회
        
        Args:
            idea_id: 아이디어 ID
            
        Returns:
            Optional[BrainstormingIdea]: 아이디어 또는 None
        """
        return self.db.query(BrainstormingIdea).filter(
            BrainstormingIdea.id == idea_id
        ).first()
    
    def get_by_user(self, user_id: int, limit: int = 100, offset: int = 0) -> List[BrainstormingIdea]:
        """
        사용자의 모든 아이디어 조회 (최신순)
        
        Args:
            user_id: 사용자 ID
            limit: 최대 개수
            offset: 시작 위치
            
        Returns:
            List[BrainstormingIdea]: 아이디어 리스트
        """
        return self.db.query(BrainstormingIdea).filter(
            BrainstormingIdea.user_id == user_id
        ).order_by(
            desc(BrainstormingIdea.created_at)
        ).limit(limit).offset(offset).all()
    
    def count_by_user(self, user_id: int) -> int:
        """
        사용자의 아이디어 총 개수
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            int: 아이디어 개수
        """
        return self.db.query(BrainstormingIdea).filter(
            BrainstormingIdea.user_id == user_id
        ).count()
    
    def delete(self, idea_id: int) -> bool:
        """
        아이디어 삭제
        
        Args:
            idea_id: 아이디어 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        idea = self.get_by_id(idea_id)
        if not idea:
            return False
        
        self.db.delete(idea)
        self.db.commit()
        return True
    
    def is_owner(self, idea_id: int, user_id: int) -> bool:
        """
        아이디어 소유자 확인
        
        Args:
            idea_id: 아이디어 ID
            user_id: 사용자 ID
            
        Returns:
            bool: 소유자 여부
        """
        idea = self.get_by_id(idea_id)
        return idea is not None and idea.user_id == user_id
