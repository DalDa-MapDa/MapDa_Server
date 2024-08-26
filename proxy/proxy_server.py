from fastapi import APIRouter, Request, Response, HTTPException
import httpx

router = APIRouter()

@router.api_route("/", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request):
    # 타깃 URL 쿼리 파라미터에서 가져오기
    target_url = request.query_params.get("target_url")
    if not target_url:
        raise HTTPException(status_code=400, detail="target_url parameter is required")

    method = request.method
    headers = {key: value for key, value in request.headers.items()
               if key.lower() not in ["host", "accept-encoding"]}  # Host 및 Accept-Encoding 제거

    # User-Agent 설정
    headers['User-Agent'] = headers.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36')
    
    # Referer는 필요에 따라 설정
    if 'referer' not in headers:
        headers['Referer'] = 'https://example.com'  # 원하는 대로 설정

    body = await request.body()

    async with httpx.AsyncClient() as client:
        response = await client.request(method, target_url, headers=headers, content=body)

    # CORS 허용을 위한 헤더 추가
    response_headers = dict(response.headers)
    response_headers['Access-Control-Allow-Origin'] = '*'

    return Response(content=response.content, status_code=response.status_code, headers=response_headers)

