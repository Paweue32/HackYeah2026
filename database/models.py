from sqlalchemy import Column, Integer, String, Float
from .database import Base

class Ways(Base):
    __tablename__ = "ways"

    way_id = Column(Integer, primary_key=True, index=True)
    start_node_id = Column(Integer, index=True)
    start_node_lat = Column(Integer, index=True)
    start_node_lon = Column(Integer, index=True)
    end_node_id = Column(Integer, index=True)
    end_node_lat = Column(Integer, index=True)
    end_node_lon = Column(Integer, index=True)
    node_amount = Column(Integer, index=True)
    distance = Column(Integer, index=True)
    way_rating = Column(Float, index=True)