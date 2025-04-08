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


# --- Modele Pilotów (Remotes) ---

class RemoteBase(BaseModel):
    """Model bazowy dla pilota."""
    name: str = Field(..., description="Nazwa pilota (np. 'Pilot bramowy główny')")
    user_id: int = Field(..., description="ID użytkownika, do którego przypisany jest pilot")
    barrier_id: str = Field(..., description="ID szlabanu, do którego pilot ma dostęp")

class RemoteCreate(RemoteBase):
    """Model do tworzenia nowego pilota."""
    pass

class RemoteResponse(RemoteBase):
    """Model odpowiedzi dla pilota."""
    id: int = Field(..., description="ID pilota w bazie danych")
    remote_id: str = Field(..., description="Unikalny identyfikator pilota w formacie hex")
    created_at: str = Field(..., description="Data utworzenia pilota (ISO 8601)")
    last_counter: int = Field(..., description="Ostatni zarejestrowany licznik pilota")

class RemoteConfigResponse(RemoteResponse):
    """Model pełnej odpowiedzi dla pilota, zawierający również klucze kryptograficzne."""
    aes_key: str = Field(..., description="Klucz AES w formacie hex")
    hmac_key: str = Field(..., description="Klucz HMAC w formacie hex")
    iv: str = Field(..., description="Wektor inicjalizacyjny w formacie hex")

# Poprawiona definicja modelu żądania weryfikacji
class RemoteVerifyRequest(BaseModel):
    """Model żądania weryfikacji pilota."""
    barrier_id: str = Field(..., description="ID szlabanu, dla którego należy zweryfikować dostęp")
    encrypted_data: str = Field(..., description="Zaszyfrowana wiadomość w formacie hex")


class RemoteVerifyResponse(BaseModel):
    """Model odpowiedzi weryfikacji pilota."""
    access_granted: bool = Field(..., description="Czy dostęp jest przyznany")
    reason: Optional[str] = None