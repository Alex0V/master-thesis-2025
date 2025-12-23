from sqlalchemy import Column, String, Text, DECIMAL, TIMESTAMP, func
from app.models.base import Base

class SystemConfig(Base):
    __tablename__ = "system_config"

    key_name = Column(String(50), primary_key=True)
    value_num = Column(DECIMAL(10, 2), nullable=False)
    description = Column(Text)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())