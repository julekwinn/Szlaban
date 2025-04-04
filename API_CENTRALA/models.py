# models.py
# -*- coding: utf-8 -*-

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict

# --- Modele Zdarzeń (Events) ---

class BarrierEventBase(BaseModel):
    barrier_id: str
    event_type: str
    trigger_method: str
    timestamp: str # ISO 8601 string from controller
    user_id: Optional[str] = None
    success: bool
    details: Optional[str] = None
    failed_action: Optional[str] = None

class BarrierEventDBInput(BarrierEventBase):
    """Model zdarzenia przychodzącego od kontrolera."""
    pass

class BarrierEventDBResponse(BarrierEventBase):
    """Model zdarzenia zwracanego przez API centrali."""
    id: int
    received_at: str # ISO 8601 string from central server

# --- Modele Użytkowników (Users) ---

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    """Model do tworzenia nowego użytkownika."""
    password: str

class UserResponse(UserBase):
    """Model odpowiedzi dla użytkownika (bez hasła)."""
    id: int

# --- Modele Szlabanów (Barriers) ---

class BarrierBase(BaseModel):
    barrier_id: str
    controller_url: str

class BarrierCreate(BarrierBase):
    """Model do dodawania nowego szlabanu."""
    pass

class BarrierResponse(BarrierBase):
    """Model odpowiedzi dla szlabanu."""
    id: int

# --- Modele Uprawnień (Permissions) ---

class PermissionBase(BaseModel):
    username: str
    barrier_id: str

class PermissionCreate(PermissionBase):
    """Model do nadawania uprawnień."""
    permission_level: str

    @field_validator('permission_level')
    def v_perm_level(cls, v):
        allowed = {'operator', 'technician'}
        if v not in allowed:
            raise ValueError(f'must be one of {allowed}')
        return v

class PermissionResponse(PermissionBase):
    """Model odpowiedzi dla uprawnienia."""
    id: int
    user_id: int
    permission_level: str

# --- Modele Odpowiedzi dla Użytkownika Końcowego ---

class MyBarrierResponse(BaseModel):
    """Model szlabanu zwracany w /api/my/barriers."""
    barrier_id: str
    controller_url: str
    permission_level: str