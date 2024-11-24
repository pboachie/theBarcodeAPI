from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class PytestModule(Base):
    __tablename__ = 'pytest_modules'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    path = Column(String, unique=True, nullable=False)
    test_count = Column(Integer, default=0)