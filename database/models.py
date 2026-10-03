from sqlalchemy import Column, Integer, String
from .database import Base

class Ways(Base):
    __tablename__ = "ways"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    highway_type = Column(String, unique=True, index=True)
    surface = Column(String, unique=True, index=True)
    maxspeed = Column(String, unique=True, index=True)
    geometry = Column(String, unique=True, index=True)
    tags = Column(String, unique=True, index=True)