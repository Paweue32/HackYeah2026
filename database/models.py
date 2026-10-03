from sqlalchemy import Column, Integer, String, Float, JSON
from .database import Base

class Ways(Base):
    __tablename__ = "ways"

    way_id = Column(Integer, primary_key=True, index=True)
    nodes = Column(JSON)
    coordinates = Column(JSON)
    distance = Column(Integer, index=True)
    way_rating = Column(Float, index=True)