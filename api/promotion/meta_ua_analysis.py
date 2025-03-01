from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from models import Campaign, SessionLocal  # models.py에 정의된 Campaign, SessionLocal 임포트
from datetime import datetime, timedelta

router = APIRouter()

# 10분 이내인 경우에만 상태 변경을 허용 (10분)
MATCH_EXPIRE_TIME = timedelta(minutes=10)

@router.get("/promotion", tags=["promotion"])
async def promotion(request: Request, utm_source: str, utm_medium: str, utm_campaign: str, utm_content: str):
    """
    메타 UA 캠페인 유입 시 호출되는 엔드포인트입니다.
    - 쿼리 파라미터(utm_source, utm_medium, utm_campaign, utm_content)와 x-real-ip 값을 파싱하여 DB에 저장합니다.
    - 기본 상태는 'Converted'로 저장됩니다.
    """
    # x-real-ip 추출 (없을 경우 클라이언트의 host 사용)
    x_real_ip = request.headers.get("x-real-ip", request.client.host)
    
    # DB에 캠페인 정보 저장 (상태 기본값은 'Converted')
    db = SessionLocal()
    new_campaign = Campaign(
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        x_real_ip=x_real_ip,
        status="Converted"
    )
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    db.close()
    
    return JSONResponse(content={
        "message": "Campaign data stored successfully",
        "campaign_id": new_campaign.id
    })

@router.get("/promotion/status/app_open", tags=["promotion"])
async def campaign_app_open(request: Request):
    """
    앱 실행 시 호출되는 엔드포인트입니다.
    - 요청된 x-real-ip와 DB의 campaign_table에서 생성된 시간이 현재 기준 10분 이내인 레코드 중 가장 최신의 값을 찾아 상태를 'APP_OPEN'으로 업데이트합니다.
    - 단, 이미 상태가 'MATCH'인 경우에는 변경하지 않습니다.
    - 내부 에러가 발생하더라도 무조건 200 OK를 반환하며, 결과 메시지를 응답 본문에 포함합니다.
    """
    response = {"message": ""}
    try:
        x_real_ip = request.headers.get("x-real-ip", request.client.host)
        db = SessionLocal()
        now = datetime.utcnow()
        expire_time = now - MATCH_EXPIRE_TIME

        # x_real_ip와 생성시간 조건에 맞는 레코드를 최신순으로 조회
        campaign_record = db.query(Campaign).filter(
            Campaign.x_real_ip == x_real_ip,
            Campaign.created_at >= expire_time
        ).order_by(Campaign.created_at.desc()).first()

        if campaign_record:
            # 이미 MATCH 상태라면 변경하지 않음
            if campaign_record.status != "MATCH":
                campaign_record.status = "APP_OPEN"
                db.commit()
                db.refresh(campaign_record)
                response["message"] = "Campaign status updated to APP_OPEN."
            else:
                response["message"] = "Campaign already in MATCH status; not updated to APP_OPEN."
        else:
            response["message"] = "No campaign record found within the valid time window."
    except Exception as e:
        response["message"] = f"Error occurred: {str(e)}"
    finally:
        try:
            db.close()
        except:
            pass

    return JSONResponse(content=response)

@router.post("/promotion/status/match", tags=["promotion"])
async def campaign_match(request: Request):
    """
    소셜 로그인 성공 후 호출되는 엔드포인트입니다.
    - 미들웨어를 통해 받은 사용자 UUID(request.state.user_uuid)를 사용합니다.
    - 요청된 x-real-ip와 DB의 campaign_table에서 생성된 시간이 현재 기준 10분 이내인 레코드 중 가장 최신의 값을 찾아,
      상태를 'MATCH'로 업데이트하고 match_UUID 컬럼에 해당 UUID를 저장합니다.
    - 이미 상태가 'MATCH'인 경우에는 변경하지 않으며, 10분이 초과된 레코드는 업데이트하지 않습니다.
    - 내부 에러 발생 여부와 관계없이 200 OK를 반환하며, 결과 메시지를 응답 본문에 포함합니다.
    """
    response = {"message": ""}
    try:
        # 인증 미들웨어를 통해 설정된 사용자 UUID (예: request.state.user_uuid)
        user_uuid = request.state.user_uuid  # 미들웨어에서 설정되어 있어야 함
        x_real_ip = request.headers.get("x-real-ip", request.client.host)
        db = SessionLocal()
        now = datetime.utcnow()
        expire_time = now - MATCH_EXPIRE_TIME

        campaign_record = db.query(Campaign).filter(
            Campaign.x_real_ip == x_real_ip,
            Campaign.created_at >= expire_time
        ).order_by(Campaign.created_at.desc()).first()

        if campaign_record:
            if campaign_record.status != "MATCH":
                campaign_record.status = "MATCH"
                campaign_record.match_UUID = user_uuid
                db.commit()
                db.refresh(campaign_record)
                response["message"] = "Campaign status updated to MATCH."
            else:
                response["message"] = "Campaign is already in MATCH status."
        else:
            response["message"] = "No campaign record found within the valid time window."
    except Exception as e:
        response["message"] = f"Error occurred: {str(e)}"
    finally:
        try:
            db.close()
        except:
            pass

    return JSONResponse(content=response)
