from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Text
)

from app.database import Base

class Message(Base):

    __tablename__ = "messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id")
    )

    role = Column(String(50))

    content = Column(Text)