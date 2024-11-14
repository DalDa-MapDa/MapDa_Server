from fastapi import APIRouter, HTTPException, Request, Form, Query
from sqlalchemy.orm import Session
from data.university_KorEng import UNIVERSITY_KOR_ENG_DATA  # 대학 한글-영문 데이터
from data.university_info import UNIVERSITY_INFO
from models import SessionLocal, User  # User 모델 임포트
from datetime import datetime
from typing import Optional

router = APIRouter()


@router.patch("/api/v1/userinfo/update_userinfo", tags=["User"])
async def update_user_info(
    request: Request,
    nickname: Optional[str] = Form(None),
    university: Optional[str] = Form(None),
    profile_number: Optional[int] = Form(None)
):
    db: Session = SessionLocal()
    try:
        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid

        # 사용자 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 닉네임 업데이트
        if nickname is not None:
            user.nickname = nickname

        # 학교 이름 업데이트 (한글 이름 -> 영문 이름 변환)
        if university is not None:
            if university not in UNIVERSITY_KOR_ENG_DATA:
                raise HTTPException(
                    status_code=400,
                    detail=f"'{university}'는 유효한 대학 이름이 아닙니다."
                )
            user.university = UNIVERSITY_KOR_ENG_DATA[university]

        # 프로필 번호 업데이트
        if profile_number is not None:
            user.profile_number = profile_number

        user.updated_at = datetime.utcnow()  # 업데이트 시간 설정

        # 변경 사항을 커밋
        db.commit()
        db.refresh(user)  # 업데이트된 사용자 정보 반환

        return {
            "uuid": user.uuid,
            "nickname": user.nickname,
            "university": user.university,
            "profile_number": user.profile_number
        }

    except HTTPException as e:
        raise e  # 이미 발생한 HTTPException을 그대로 다시 발생시킴
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()


@router.post("/api/v1/userinfo/register_complete", tags=["User"])
async def register_complete(
    request: Request,
    nickname: str = Form(...),
    university: str = Form(...)
):
    db: Session = SessionLocal()
    try:
        # 인증된 사용자 UUID 가져오기 (토큰 검증을 위해 미들웨어 사용)
        user_uuid = request.state.user_uuid

        # 사용자 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 닉네임 업데이트
        user.nickname = nickname

        # 학교 이름 업데이트 (한글 이름 -> 영문 이름 변환)
        if university not in UNIVERSITY_KOR_ENG_DATA:
            raise HTTPException(
                status_code=400,
                detail=f"'{university}'는 유효한 대학 이름이 아닙니다."
            )
        user.university = UNIVERSITY_KOR_ENG_DATA[university]

        user.status = "Active"  # 상태를 Active로 변경
        user.updated_at = datetime.utcnow()  # 업데이트 시간 기록

        # 변경 사항 커밋
        db.commit()
        db.refresh(user)  # 업데이트된 정보 반환 준비

        return {
            "uuid": user.uuid,
            "nickname": user.nickname,
            "university": user.university,
            "status": user.status,
            "updated_at": user.updated_at
        }

    except HTTPException as e:
        raise e  # 이미 발생한 HTTPException을 그대로 다시 발생시킴
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()


@router.get("/api/v1/userinfo/inquire", tags=["User"])
async def inquire_user_info(
    request: Request,
):
    db: Session = SessionLocal()
    try:
        # 인증된 사용자 UUID 가져오기 (토큰 검증을 위해 미들웨어 사용)
        user_uuid = request.state.user_uuid

        # 사용자 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 유저 정보 (nickname, university, profile_number, provider_profile_image) 가져오기
        user_info = {
            "uuid": user.uuid,
            "nickname": user.nickname,
            "university": user.university,
            "profile_number": user.profile_number,
            "provider_profile_image": user.provider_profile_image
        }

        # university 정보가 있으면 위치 정보도 개별 필드로 추가
        if user.university and user.university in UNIVERSITY_INFO:
            university_location = UNIVERSITY_INFO.get(user.university)
            user_info.update({
                "univ_sw_lat": university_location.get("sw_lat"),
                "univ_sw_lng": university_location.get("sw_lng"),
                "univ_ne_lat": university_location.get("ne_lat"),
                "univ_ne_lng": university_location.get("ne_lng"),
                "univ_center_lat": university_location.get("center_lat"),
                "univ_center_lng": university_location.get("center_lng"),
            })
        else:
            # university가 없거나 위치 정보가 없는 경우 위치 필드를 None으로 설정
            user_info.update({
                "univ_sw_lat": None,
                "univ_sw_lng": None,
                "univ_ne_lat": None,
                "univ_ne_lng": None,
                "univ_center_lat": None,
                "univ_center_lng": None
            })

        # university를 한글로 변환
        for kor_name, eng_name in UNIVERSITY_KOR_ENG_DATA.items():
            if user_info["university"] == eng_name:
                user_info["university"] = kor_name
                break

        return user_info

    except HTTPException as e:
        raise e  # 이미 발생한 HTTPException을 그대로 다시 발생시킴
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()


@router.get("/api/v1/userinfo/check_nickname", tags=["User"])
async def check_nickname(
    request: Request,
    name: str = Query(...)
):
    db: Session = SessionLocal()
    try:
        # 인증된 사용자 UUID 가져오기 (토큰 검증을 위해 미들웨어 사용)
        user_uuid = request.state.user_uuid

        # 중복 여부 확인
        nickname_exists = (
            db.query(User)
            .filter(User.nickname == name, User.status != 'Deleted')
            .first()
        )

        if nickname_exists:
            # 중복인 경우, 409 상태 코드 반환
            raise HTTPException(status_code=409, detail="닉네임이 이미 사용 중입니다.")

        # 중복이 아닌 경우, 200 상태 코드 반환
        return {
            "status": "사용 가능한 닉네임입니다."
        }

    except HTTPException as e:
        # 이미 발생한 HTTPException을 그대로 다시 발생시킵니다.
        raise e
    except Exception as e:
        # 서버 오류 처리
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()