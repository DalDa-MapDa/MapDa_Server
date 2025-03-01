from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from models import Campaign, SessionLocal  # models.py에 정의된 Campaign, SessionLocal 임포트

router = APIRouter()

@router.get("/promotion", tags=["promotion"])
async def promotion(request: Request, utm_source: str, utm_medium: str, utm_campaign: str, utm_content: str):
    """
    메타 UA 캠페인 유입 시 호출되는 엔드포인트입니다.
    - 쿼리 파라미터(utm_source, utm_medium, utm_campaign, utm_content)와 x-real-ip 값을 파싱하여 DB에 저장합니다.
    - 이후 웹페이지에서 리디렉션을 처리할 예정입니다.
    """
    # x-real-ip 추출 (없을 경우 클라이언트의 host 사용)
    x_real_ip = request.headers.get("x-real-ip", request.client.host)
    
    # DB에 캠페인 정보 저장
    db = SessionLocal()
    new_campaign = Campaign(
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        x_real_ip=x_real_ip
    )
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    db.close()
    
    return JSONResponse(content={
        "message": "Campaign data stored successfully",
        "campaign_id": new_campaign.id
    })

@router.post("/promotion/match", tags=["promotion"])
async def campaign_match(request: Request):
    """
    회원가입 시 호출되는 엔드포인트입니다.
    - 요청 헤더의 x-real-ip를 기준으로 DB의 campaign_table에서 해당 레코드가 있는지 조회합니다.
    - 매칭되는 레코드가 있으면 match 컬럼을 True로 업데이트한 후 결과를 반환합니다.
    """
    x_real_ip = request.headers.get("x-real-ip", request.client.host)
    
    db = SessionLocal()
    campaign_record = db.query(Campaign).filter(
        Campaign.x_real_ip == x_real_ip,
        Campaign.match == False
    ).first()
    
    if campaign_record:
        campaign_record.match = True
        db.commit()
        db.refresh(campaign_record)
        result = True
    else:
        result = False
    db.close()
    
    return JSONResponse(content={"match": result})
