import jwt
from fastapi import Request

from src.utils.exceptions import UnauthorizedException


class AuthService:
    @staticmethod
    def get_current_user(request: Request):
        # 1. Lấy header Authorization
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            raise UnauthorizedException("Authorization header missing")

        # 2. Kiểm tra đúng định dạng "Bearer <token>"
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedException("Invalid Authorization header format")

        # 3. Lấy token
        token = auth_header.split(" ")[1]

        # 4. Decode token (không verify signature)
        try:
            decoded = jwt.decode(
                token,
                options={"verify_signature": False}
            )
        except jwt.DecodeError:
            raise UnauthorizedException("Invalid token")

        # 5. Lấy userId ra
        user_id = decoded.get("userId")
        if not user_id:
            raise UnauthorizedException("Invalid token")

        return user_id
