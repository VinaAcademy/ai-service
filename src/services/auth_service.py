import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.utils.exceptions import UnauthorizedException

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class AuthService:
    def get_current_user(self, token: str = Depends(oauth2_scheme)):
        if not token:
            raise UnauthorizedException("Missing authentication token")
        decoded = jwt.decode(self, token, options={"verify_signature": False})
        return decoded["userId"]
