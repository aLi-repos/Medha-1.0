from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.auth import TokenResponse
from app.services.user_service import user_service


class AuthService:
    """Issues local, short-lived JWTs for authenticated users."""

    def login(
        self,
        db: Session,
        username: str,
        password: str,
        user_id: str | None = None,
    ) -> TokenResponse | None:
        user = user_service.authenticate(db, username, password, user_id=user_id)
        if user is None:
            return None

        # Effective default security mode is determined by the user's role.
        user_service.ensure_role_security_floor(db, user)

        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_expiration_minutes
        )
        token = jwt.encode(
            {
                "sub": user.username,
                "uid": user.user_id,
                "role": user.role,
                "iat": datetime.now(timezone.utc),
                "exp": expires_at,
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        return TokenResponse(access_token=token)


auth_service = AuthService()
