from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
import re


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (at least 8 characters)")

    @field_validator("full_name")
    def clean_name(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return cleaned

    @field_validator("email")
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("password")
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class SignupResponse(BaseModel):
    message: str
    email: str


class VerifyOTPRequest(BaseModel):
    email: EmailStr = Field(..., description="User's registered email")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")

    @field_validator("email")
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("otp")
    def validate_otp_digits(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned.isdigit() or len(cleaned) != 6:
            raise ValueError("OTP must be exactly 6 numeric digits")
        return cleaned


class VerifyOTPResponse(BaseModel):
    message: str
    email: str
    is_verified: bool


class ResendOTPRequest(BaseModel):
    email: EmailStr = Field(..., description="User's registered email")

    @field_validator("email")
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class ResendOTPResponse(BaseModel):
    message: str
    email: str
    cooldown_seconds: int


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's registered email")
    password: str = Field(..., min_length=1, description="Password")

    @field_validator("email")
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    message: str

