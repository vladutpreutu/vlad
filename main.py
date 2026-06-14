import os
import sqlite3
import jwt
import bcrypt
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
SECRET_KEY = os.environ.get("SECRET_KEY", "o-cheie-secreta-foarte-lunga")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
EXPIRARE_TOKEN_MINUTE = int(os.environ.get("EXPIRARE_TOKEN_MINUTE", 30))

# ---------------------------------------------------------------------------
# Baza de date
# ---------------------------------------------------------------------------

def initializeaza_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute("CREATE TABLE IF NOT EXISTS utilizatori (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, parola_hash TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS sarcini (id INTEGER PRIMARY KEY AUTOINCREMENT, titlu TEXT NOT NULL, descriere TEXT, finalizata INTEGER DEFAULT 0, utilizator_id INTEGER NOT NULL, FOREIGN KEY (utilizator_id) REFERENCES utilizatori(id))")
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

@asynccontextmanager
async def durata_de_viata(app: FastAPI):
    initializeaza_db()
    yield

app = FastAPI(title="Gestionar de sarcini", lifespan=durata_de_viata)

app.add_middleware(
    CORSMiddleware,
