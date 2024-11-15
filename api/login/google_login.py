import os
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session
from models import SessionLocal, Token, User
from api.login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)
import requests

router = APIRouter()

# Load environment variables
load_dotenv()

GOOGLE_CLIENT_IDS = os.getenv("GOOGLE_CLIENT_IDS", "").split(",")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


class GoogleLoginData(BaseModel):
    idToken: str
    accessToken: str


@router.post("/login/google", tags=["Login"])
async def google_login(data: GoogleLoginData, response: Response):
    db: Session = SessionLocal()
    try:
        # Verify ID Token
        id_info = verify_id_token(data.idToken)

        # Check client ID
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            raise HTTPException(status_code=400, detail="Invalid client ID")

        # Extract user information
        provider_id = id_info['sub']
        user_data = {
            "email": id_info.get('email'),
            "provider_profile_image": id_info.get('picture'),
            "provider_user_name": id_info.get('name')
        }

        # Check if user exists
        user = get_user_by_provider(db, 'GOOGLE', provider_id)

        if not user:
            # Create a new user
            user = create_user(
                db,
                email=user_data["email"],
                provider_type='GOOGLE',
                provider_id=provider_id,
                provider_profile_image=user_data["provider_profile_image"],
                provider_user_name=user_data["provider_user_name"],
                status='Need_Register'
            )
            message = "Need_Register"
            response.status_code = 201
        else:
            # Update user fields if changed
            updated_fields = {
                k: v for k, v in user_data.items() if v is not None and getattr(user, k) != v
            }
            if updated_fields:
                user = update_user(db, user, **updated_fields)

            if user.status == 'Need_Register':
                message = "Need_Register"
                response.status_code = 202
            elif user.status == 'Active':
                message = "로그인 성공"
                response.status_code = 200
            else:
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # Generate tokens
        access_token = create_access_token(uuid=user.uuid)
        refresh_token = create_refresh_token()

        # Update tokens in database
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='GOOGLE',
            provider_access_token=data.accessToken
        )

        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")
    finally:
        db.close()


@router.delete("/unregister/google", tags=["Login"])
def google_unregister_function(user_uuid: str):
    db: Session = SessionLocal()
    try:
        # Get token entry
        token_entry = db.query(Token).filter(Token.uuid == user_uuid).first()
        if not token_entry:
            raise HTTPException(status_code=404, detail="User not found")

        user_access_token = token_entry.provider_access_token

        # Revoke token
        revoke_url = f"https://accounts.google.com/o/oauth2/revoke?token={user_access_token}"
        revoke_response = requests.post(revoke_url)

        if revoke_response.status_code != 200:
            raise HTTPException(status_code=revoke_response.status_code, detail="Failed to revoke Google token")

        # Update user and token status
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if user:
            user.status = 'Deleted'
            db.commit()

        token_entry.status = 'Deleted'
        db.commit()

        return {"message": "Google account successfully unregistered"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unregistering Google account: {str(e)}")
    finally:
        db.close()


def verify_id_token(id_token_str: str) -> dict:
    """Verify and decode Google ID Token"""
    try:
        return id_token.verify_oauth2_token(id_token_str, google_requests.Request(), None)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID Token")
