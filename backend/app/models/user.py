import uuid

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    outline_ai_model = Column(String(80), nullable=True)
    constitution_ai_model = Column(String(80), nullable=True)
    writing_ai_model = Column(String(80), nullable=True)
    assistant_ai_model = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    books = relationship("Book", back_populates="owner", cascade="all, delete-orphan")
