from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserAiModelsOut(BaseModel):
    outline_ai_model: str | None = None
    constitution_ai_model: str | None = None
    writing_ai_model: str | None = None
    assistant_ai_model: str | None = None


class UserAiModelsPatch(BaseModel):
    outline_ai_model: str | None = Field(default=None, max_length=80)
    constitution_ai_model: str | None = Field(default=None, max_length=80)
    writing_ai_model: str | None = Field(default=None, max_length=80)
    assistant_ai_model: str | None = Field(default=None, max_length=80)


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    ai_models: UserAiModelsOut

    class Config:
        from_attributes = True

    @classmethod
    def from_user(cls, user) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            ai_models=UserAiModelsOut(
                outline_ai_model=user.outline_ai_model,
                constitution_ai_model=user.constitution_ai_model,
                writing_ai_model=user.writing_ai_model,
                assistant_ai_model=user.assistant_ai_model,
            ),
        )
