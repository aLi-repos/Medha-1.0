from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    OPERATOR = "operator"
    ENGINEER = "engineer"
    SENIOR_ENGINEER = "senior_engineer"
    MANAGER = "manager"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    HR = "hr"
    JUNIOR_ENGINEER = "junior_engineer"
    MONITOR = "monitor"


# Authorized demo-organization records: user_id -> (username, role).
# UID is the authoritative identity; signup validates UID + selected role
# against this table. Duplicate usernames remain allowed elsewhere.
AUTHORIZED_ORG_RECORDS: dict[str, tuple[str, Role]] = {
    "SE00503": ("nagarjuna", Role.SENIOR_ENGINEER),
    "AD00637": ("lokesh", Role.ADMIN),
    "MD00574": ("Ali", Role.MANAGER),
    "OP00303": ("Balaji", Role.OPERATOR),
    "JE00589": ("keerthi", Role.JUNIOR_ENGINEER),
    "MO00579": ("saniya", Role.MONITOR),
}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    # Optional: authoritative account identity. Required in practice when
    # two accounts share the same username (user_id disambiguates).
    user_id: str | None = Field(default=None, max_length=20)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=256)
    # Organization-assigned permanent identity (optional; generated if omitted).
    user_id: str | None = Field(default=None, max_length=20)
    # Parsed for provisioning UIs but never trusted from normal self-signup —
    # the server assigns roles. Kept for API compatibility.
    role: Role = Role.OPERATOR


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    role: Role
    preferred_security_mode: str = "standard"


class UsernameUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
