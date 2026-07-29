from pydantic import BaseModel
from typing import Optional

class LinkedAccountCreate(BaseModel):
    platform: str
    status: str
    username: str
    password: Optional[str] = None
    apiKey: Optional[str] = None
    domain: Optional[str] = None

class LinkedAccountOut(BaseModel):
    id: str  # _id 轉成 id
    platform: str
    status: str
    username: str
    apiKey: Optional[str] = None
    avatar_url: Optional[str] = None

class LinkedAccountInDB(LinkedAccountCreate):
    id: str   # 存Mongo時用id


# from pydantic import BaseModel
# from typing import Optional
# from datetime import datetime


# class LinkedAccountBase(BaseModel):
#     clerk_id: str
#     name: str
#     platform: str
#     #platformUid: str
#     #accessToken: Optional[str] = None
#     apiKey: Optional[str] = None
#     #linkedTime: Optional[datetime] = None
#     status: str
    


# class LinkedAccountCreate(LinkedAccountBase):
#     clerk_id: str


# class LinkedAccountCreate(LinkedAccountBase):
#     clerk_id: str


# class LinkedAccountInDB(LinkedAccountCreate):
#     clerk_id : str
