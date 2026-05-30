from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from app.database import Base

class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    title = Column(String(255))

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )