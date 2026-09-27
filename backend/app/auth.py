from enum import Enum
from typing import Callable, Optional
from fastapi import Depends, Header, HTTPException, status
from app.config import settings


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    INSTITUTION_VIEWER = "institution_viewer"


def get_current_role(x_api_key: Optional[str] = Header(None)) -> UserRole:
    """
    Validates incoming request's 'x-api-key' header against configured role keys.
    Raises HTTP 401 if missing or invalid.
    """
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in 'x-api-key' header.",
        )

    clean_key = x_api_key.strip()

    # Admin matches dedicated ADMIN_API_KEY or legacy INTERNAL_API_KEY
    if clean_key in (settings.ADMIN_API_KEY, settings.INTERNAL_API_KEY):
        return UserRole.ADMIN
    elif clean_key == settings.ANALYST_API_KEY:
        return UserRole.ANALYST
    elif clean_key == settings.INSTITUTION_API_KEY:
        return UserRole.INSTITUTION_VIEWER
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )


def require_roles(*allowed_roles: UserRole) -> Callable[[UserRole], UserRole]:
    """
    FastAPI dependency factory enforcing that the authenticated user
    possesses one of the specified roles.
    Raises HTTP 403 Forbidden if the authenticated role is not allowed.
    """
    def role_checker(role: UserRole = Depends(get_current_role)) -> UserRole:
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role '{role.value}' is not permitted to perform this action.",
            )
        return role

    return role_checker


# Pre-configured role dependencies
# 1. Any valid role key (e.g. general read-only indicator feed)
verify_api_key = require_roles(
    UserRole.ADMIN,
    UserRole.ANALYST,
    UserRole.INSTITUTION_VIEWER,
)

# 2. Analyst operations: conversations, messages, reviews, explanations
require_analyst = require_roles(
    UserRole.ADMIN,
    UserRole.ANALYST,
)

# 3. Institution operations: indicator blocking
require_institution = require_roles(
    UserRole.ADMIN,
    UserRole.INSTITUTION_VIEWER,
)

# 4. Admin-only operations: simulation triggering, advanced management
require_admin = require_roles(
    UserRole.ADMIN,
)
