from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" \
               f"{os.getenv('DB_ENDPOINT')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserObject(Base):
    __tablename__ = 'user_objects'

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    user_id = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    object_name = Column(String(255), nullable=False)  # 길이 지정
    place_name = Column(String(255), nullable=False)  # 길이 지정
    image_url = Column(String(255), nullable=False)  # 여기도 필요하면 길이 지정
   

# 테이블 생성
Base.metadata.create_all(bind=engine)
