from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: str = Field(max_length=200)
    password: str = Field(min_length=6, max_length=100)
