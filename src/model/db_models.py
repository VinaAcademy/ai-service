from sqlalchemy import String, Text
from structlog.dev import Column

from src.model.base import BaseMixin, Base


class ChatHistory(Base, BaseMixin):
    __tablename__ = 'chat_histories'

    session_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    message = Column(String, nullable=False)
    response = Column(Text, nullable=False)

    def __repr__(self):
        return f"<ChatHistory(session_id={self.session_id})>"
