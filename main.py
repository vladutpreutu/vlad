import os
import sqlite3
import jwt
import bcrypt  # Adăugat pentru hashing direct
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Configurare
# ---------------------------------------------------------------------------
load_dotenv() 

DATABASE = os.environ.get("DATABASE_PATH", "sarcini.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "schimba-asta-in-productie")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
EXPIRARE_TOKEN_MINUTE = int(os.environ.get("EXPIRARE_TOKEN_MINUTE", 30))

oauth2_schema = OAuth2PasswordBearer(tokenUrl="autentificare")

# ---------------------------------------------------------------------------
# Baza de date
# ---------------------------------------------------------------------------

def initializeaza_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS utilizatori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            parola_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sarcini (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titlu TEXT NOT NULL,
            descriere TEXT,
            finalizata INTEGER DEFAULT 0,
            utilizator_id INTEGER NOT NULL,
            FOREIGN KEY (utilizator_id) REFERENCES utilizatori(id)
        )
    """)
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()

@asynccontextmanager
async def durata_de_viata(app: FastAPI):
    initializeaza_db()
    yield

# ---------------------------------------------------------------------------
# Aplicația
# ---------------------------------------------------------------------------

app = FastAPI(title="Gestionar de sarcini", version="1.0.0", lifespan=durata_de_viata)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Modele Pydantic
# ---------------------------------------------------------------------------

class UtilizatorInregistrare(BaseModel):
    email: str = Field(min_length=5, max_length=100)
    parola: str = Field(min_length=8, max_length=72) 

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Adresa de email nu este validă.")
        return v.lower()

class SarcinaCreare(BaseModel):
    titlu: str = Field(min_length=1, max_length=200)
    descriere: Optional[str] = Field(default=None, max_length=1000)

# ---------------------------------------------------------------------------
# Funcții utilitare (Hash cu bcrypt direct)
# ---------------------------------------------------------------------------

def hasheaza_parola(parola: str) -> str:
    parola_bytes = parola[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(parola_bytes, salt)
    return hash_bytes.decode('utf-8')

def verifica_parola(parola: str, hash_parola: str) -> bool:
    parola_bytes = parola[:72].encode('utf-8')
    hash_bytes = hash_parola.encode('utf-8')
    return bcrypt.checkpw(parola_bytes, hash_bytes)

def creeaza_token(date: dict) -> str:
    date_copie = date.copy()
    date_copie["exp"] = datetime.now(timezone.utc) + timedelta(minutes=EXPIRARE_TOKEN_MINUTE)
    return jwt.encode(date_copie, SECRET_KEY, algorithm=ALGORITHM)
