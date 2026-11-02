
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Data required when registering a new account
class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# Data required when logging in
class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# User information returned by the API
class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


# Authentication token response
class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse
