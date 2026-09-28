"""FastAPI authentication and database dependencies."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from api.security import decode_access_token_claims
from database.user_models import SessionLocal, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token_claims(token)
    except ValueError:
        raise credentials_error
    user = db.get(User, claims["user_id"])
    if (
        not user
        or not user.is_active
        or int(user.token_version or 0) != claims["token_version"]
    ):
        raise credentials_error
    return user
