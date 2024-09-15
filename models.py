from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

DATABASE_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" \
               f"{os.getenv('DB_ENDPOINT')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generate_uuid(prefix: str, date: datetime, seq_num: int) -> str:
    date_str = date.strftime('%Y%m%d')  # YYYYMMDD 형식
    return f"{prefix}{date_str}{seq_num:03d}"  # 순번을 3자리로 설정

class UserObject(Base):
    __tablename__ = 'user_objects'

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(20), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    object_name = Column(String(255), nullable=False)
    place_name = Column(String(255), nullable=False)
    image_url = Column(String(255), nullable=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.uuid:
            # 해당 일자의 기존 레코드 수를 세어 순번을 만듭니다.
            session = SessionLocal()
            seq_num = session.query(func.count(UserObject.id)).filter(
                func.date(UserObject.created_at) == datetime.utcnow().date()).scalar() + 1
            session.close()
            self.uuid = generate_uuid("U", datetime.utcnow(), seq_num)

class Place(Base):
    __tablename__ = 'places_data'
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(20), unique=True, nullable=False, index=True)
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
    indoor_images = relationship("PlaceIndoor", backref="place")
    outdoor_images = relationship("PlaceOutdoor", backref="place")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.uuid:
            # 해당 일자의 기존 레코드 수를 세어 순번을 만듭니다.
            session = SessionLocal()
            seq_num = session.query(func.count(Place.id)).filter(
                func.date(Place.created_at) == datetime.utcnow().date()).scalar() + 1
            session.close()
            self.uuid = generate_uuid("P", datetime.utcnow(), seq_num)

class PlaceIndoor(Base):
    __tablename__ = 'place_indoor'
    
    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey('places_data.id'), nullable=False)
    image_url = Column(String(255), nullable=False)

class PlaceOutdoor(Base):
    __tablename__ = 'place_outdoor'
    
    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey('places_data.id'), nullable=False)
    image_url = Column(String(255), nullable=False)

# 테이블 생성
Base.metadata.create_all(bind=engine)
