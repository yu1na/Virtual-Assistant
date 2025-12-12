"""
브레인스토밍 아이디어 모델
"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.session import Base


class BrainstormingIdea(Base):
    """브레인스토밍 아이디어 모델"""
    
    __tablename__ = "brainstorming_ideas"
    
    # 기본 필드
    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="아이디어 ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="사용자 ID")
    
    # 아이디어 내용
    title = Column(String(255), nullable=False, comment="아이디어 제목")
    description = Column(Text, nullable=False, comment="아이디어 상세 내용 (JSON 형식)")
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")
    
    # Relationship (필요 시)
    # user = relationship("User", back_populates="brainstorming_ideas")
    
    def __repr__(self):
        return f"<BrainstormingIdea(id={self.id}, user_id={self.user_id}, title={self.title[:30]}...)>"
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
