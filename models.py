from sqlalchemy import Time, create_engine, Column, Integer, String, Float, DateTime, Date, Enum, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv
import os
from datetime import datetime
from data.university_info import UNIVERSITY_INFO
load_dotenv()


# Database connection setup
DATABASE_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" \
               f"{os.getenv('DB_ENDPOINT')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Function to generate unique IDs
def generate_uuid(prefix: str, date: datetime, seq_num: int) -> str:
    date_str = date.strftime('%Y%m%d')  # YYYYMMDD format
    return f"{prefix}{date_str}{seq_num:011d}"  # Adjusted to make total length 21 characters

# 대학 이름 목록을 가져오기 위한 함수
university_names = list(UNIVERSITY_INFO.keys())

# User model definition
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(21), unique=True, nullable=False, index=True)
    role = Column(Enum('admin', 'user', 'manager', name='user_roles'), default='user', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(Enum('Active', 'Block', 'Deleted', 'Need_Register', name='user_statuses'), default='Active', nullable=False)
    email = Column(String(255), nullable=True)
    nickname = Column(String(255), nullable=True)
    university = Column(Enum(*university_names, name='university_names'), nullable=True)
    profile_number = Column(Integer, default=1, nullable=False)
    provider_type = Column(Enum('KAKAO', 'APPLE', 'GOOGLE', name='provider_types'), nullable=True)
    provider_id = Column(String(255), nullable=False)
    provider_profile_image = Column(String(255), nullable=True)
    provider_user_name = Column(String(255), nullable=True)
    apple_real_user_status = Column(Integer, nullable=True)

    # Relationships
    tokens = relationship('Token', back_populates='user')
    user_objects = relationship('UserObject', back_populates='user')
    timetables = relationship('UserTimetable', back_populates='user')  # Relationship with UserTimetable
    contributions = relationship("PlaceContribution", back_populates="user") # 장소 정보에 대해 여러 유저가 기여할 수 있도록 설정


    # UUID generation logic
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.uuid:
            session = SessionLocal()
            seq_num = session.query(func.count(User.id)).filter(
                func.date(User.created_at) == datetime.utcnow().date()
            ).scalar() + 1
            session.close()
            self.uuid = generate_uuid("U", datetime.utcnow(), seq_num)



# Token model definition
class Token(Base):
    __tablename__ = 'tokens'

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(21), ForeignKey('users.uuid'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(Enum('Active', 'Block', 'Deleted', name='token_statuses'), default='Active', nullable=False)
    refresh_token = Column(String(255), nullable=False)
    provider_type = Column(Enum('KAKAO', 'APPLE', 'GOOGLE', name='provider_types'), nullable=True)
    provider_access_token = Column(String(255), nullable=True)
    provider_refresh_token = Column(String(255), nullable=True)

    # Relationship
    user = relationship('User', back_populates='tokens')

# UserObject model definition
class UserObject(Base):
    __tablename__ = 'user_objects'

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(String(21), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(Enum('Active', 'Block', 'Deleted', name='user_object_status'), default='Active', nullable=False)
    user_id = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    object_name = Column(String(255), nullable=False)
    place_name = Column(String(255), nullable=False)
    image_url = Column(String(255), nullable=False)
    created_uuid = Column(String(21), ForeignKey('users.uuid'), nullable=False)
    university = Column(Enum(*university_names, name='university_names'), nullable=True)  # 추가된 university 컬럼

    # Relationship
    user = relationship('User', back_populates='user_objects')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.resource_id:
            session = SessionLocal()
            seq_num = session.query(func.count(UserObject.id)).filter(
                func.date(UserObject.created_at) == datetime.utcnow().date()
            ).scalar() + 1
            session.close()
            self.resource_id = generate_uuid("UO", datetime.utcnow(), seq_num)

class PlaceMaster(Base):
    __tablename__ = "place_master"

    id = Column(Integer, primary_key=True, index=True)
    place_name = Column(String(255), nullable=False)   # 건물명
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    university = Column(Enum(*university_names, name='university_names'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 관계 설정
    contributions = relationship("PlaceContribution", back_populates="place_master")


class PlaceContribution(Base):
    __tablename__ = "place_contribution"

    id = Column(Integer, primary_key=True, index=True)
    place_master_id = Column(Integer, ForeignKey("place_master.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 장애물/편의시설 정보
    wheele_chair_accessible = Column(Integer, nullable=True) 
    rest_room_exist = Column(Integer, nullable=True)
    rest_room_floor = Column(Integer, nullable=True)
    elevator_accessible = Column(Integer, nullable=True)
    ramp_accessible = Column(Integer, nullable=True)

    # 상태/생성시간 등
    status = Column(Enum('Active', 'Block', 'Deleted', name='contribution_status'),
                    default='Active', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 관계 설정
    place_master = relationship("PlaceMaster", back_populates="contributions")
    user = relationship("User", back_populates="contributions")
    images = relationship("PlaceContributionImage", back_populates="contribution")


class PlaceContributionImage(Base):
    __tablename__ = "place_contribution_image"

    id = Column(Integer, primary_key=True, index=True)
    place_contribution_id = Column(Integer, ForeignKey("place_contribution.id"), nullable=False)
    image_url = Column(String(255), nullable=False)
    image_type = Column(Enum('indoor', 'outdoor', name='image_types'), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    contribution = relationship("PlaceContribution", back_populates="images")

# UserTimetable model definition
class UserTimetable(Base):
    __tablename__ = 'user_timetable'

    id = Column(Integer, primary_key=True, index=True)
    lname = Column(String(255), nullable=False)  # 강의 이름
    day = Column(String(10), nullable=False)  # 요일
    start_time = Column(Time, nullable=False)  # 강의 시작 시간
    end_time = Column(Time, nullable=False)  # 강의 종료 시간
    classroom = Column(String(255), nullable=True)  # 강의실 (NULL 허용)
    created_uuid = Column(String(21), ForeignKey('users.uuid'), nullable=False)  # 사용자 UUID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 최초 생성 시간
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)  # 마지막 업데이트 시간
    user_object_status = Column(Enum('Active', 'Block', 'Deleted', name='user_object_status'), default='Active', nullable=False)

    # Relationship
    user = relationship('User', back_populates='timetables')

# Create all tables in the database
Base.metadata.create_all(bind=engine)
