from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="教师=用户名，学生=姓名")
    password: str = Field(..., min_length=1, description="密码")
    class_id: Optional[int] = Field(None, description="学生登录时的班级 ID")
    school_id: Optional[int] = Field(None, description="学校 ID（教师/学校管理员/学生登录必填）")


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="学生姓名（作为用户名）")
    password: str = Field("123456", min_length=6, max_length=50, description="密码，默认 123456")
    class_id: Optional[int] = Field(None, description="班级 ID")


class PasswordRequest(BaseModel):
    old_password: str
    # 密码强度由 security.validate_password_strength 校验（至少8位+字母+数字）
    new_password: str = Field(..., min_length=1, max_length=50)
