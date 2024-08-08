from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

DATABASE_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" \
               f"{os.getenv('DB_ENDPOINT')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserObject(Base):
    __tablename__ = 'user_objects'

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    object_name = Column(String(255), nullable=False)
    place_name = Column(String(255), nullable=False)
    image_url = Column(String(255), nullable=False)

class Place(Base):
    __tablename__ = 'places_data'

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=False)
    place_name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    wheele_chait_accessible = Column(Integer, nullable=False)
    rest_room_exist = Column(Integer, nullable=True)
    rest_room_floor = Column(Integer, nullable=True)
    elevator_accessible = Column(Integer, nullable=True)
    ramp_accessible = Column(Integer, nullable=True)
    in_door_image_urls = Column(String(1000), nullable=True)
    out_door_image_urls = Column(String(1000), nullable=True)

# 테이블 생성
Base.metadata.create_all(bind=engine)
