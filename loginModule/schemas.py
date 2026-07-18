from datetime import datetime
from ninja import Schema
from typing import List, Dict, Any
from pydantic import BaseModel



class LoginUserSchema(Schema):
    username: str
    password: str

class RegisterUserSchema(Schema):
    email: str
    username: str
    password: str
    phone: str

class GetAllUserSchema(Schema):
    id: int
    username: str
    email: str
    phone: str | None

    first_name: str
    last_name: str

    is_active: bool
    is_staff: bool

    date_joined: datetime
    last_login: datetime | None
class DeleteUserSchema(Schema):
    id: int
    username: str
    email: str
class DeactivateUserSchema(Schema):
    username: str
class ActivateUserSchema(Schema):
    username: str
class GetUserSchema(Schema):
    username: str