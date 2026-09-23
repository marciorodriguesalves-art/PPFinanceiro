from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Role, User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise _CRED_EXC
    user_id = payload.get("sub")
    if user_id is None:
        raise _CRED_EXC
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise _CRED_EXC
    return user


def require_admin(current: User = Depends(get_current_user)) -> User:
    if current.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ação restrita a administradores",
        )
    return current
