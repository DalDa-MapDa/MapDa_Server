from fastapi import APIRouter, Request, Response, HTTPException
import httpx

router = APIRouter()

@router.api_route("/", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request):
    target_url = request.query_params.get("target_url")
    if not target_url:
        raise HTTPException(status_code=400, detail="target_url parameter is required")

    method = request.method
    headers = {key: value for key, value in request.headers.items() if key.lower() not in ["host", "accept-encoding"]}

    headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    headers['Referer'] = headers.get('Referer', target_url)

    body = await request.body()

    async with httpx.AsyncClient() as client:
        response = await client.request(method, target_url, headers=headers, content=body)

    # CORS 허용을 위한 헤더를 명시적으로 추가
    custom_headers = dict(response.headers)
    custom_headers.update({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE',
        'Access-Control-Allow-Headers': '*'
    })

    return Response(content=response.content, status_code=response.status_code, headers=custom_headers)
