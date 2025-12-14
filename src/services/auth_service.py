import jwt
from fastapi import Request

from src.utils.exceptions import UnauthorizedException


class AuthService:
    @staticmethod
    def get_current_user(request: Request):
        decoded = AuthService._get_decoded_jwt(request)

        # 5. Lấy userId ra
        user_id = decoded.get("userId")
        if not user_id:
            raise UnauthorizedException("Invalid token")

        return user_id

    @staticmethod
    def get_user_info(request: Request):
        decoded = AuthService._get_decoded_jwt(request)

        # Lấy thông tin user từ token
        user_info = {
            "user_id": decoded.get("userId"),
            "email": decoded.get("email"),
            "full_name": decoded.get("fullName"),
            "roles": decoded.get("roles", []),
        }
        return user_info

    @staticmethod
    def _get_decoded_jwt(request):
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
        return decoded
