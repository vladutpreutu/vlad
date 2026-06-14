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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Modele și Utilitare
# ---------------------------------------------------------------------------

class UtilizatorInregistrare(BaseModel):
    email: str = Field(min_length=5, max_length=100)
    parola: str = Field(min_length=8, max_length=72)

def hasheaza_parola(parola: str) -> str:
    return bcrypt.hashpw(parola.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verifica_parola(parola: str, hash_parola: str) -> bool:
    return bcrypt.checkpw(parola.encode('utf-8'), hash_parola.encode('utf-8'))

def creeaza_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRARE_TOKEN_MINUTE)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ---------------------------------------------------------------------------
# RUTE API (Trebuie definite INAINTE de mount)
# ---------------------------------------------------------------------------

@app.post("/inregistrare", status_code=201)
def inregistrare(user: UtilizatorInregistrare, db: sqlite3.Connection = Depends(get_db)):
    try:
        hash_p = hasheaza_parola(user.parola)
        db.execute("INSERT INTO utilizatori (email, parola_hash) VALUES (?, ?)", (user.email.lower(), hash_p))
        db.commit()
        return {"mesaj": "Utilizator creat cu succes"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email deja existent")

@app.post("/autentificare")
def autentificare(form_data: OAuth2PasswordRequestForm = Depends(), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.execute("SELECT * FROM utilizatori WHERE email = ?", (form_data.username.lower(),))
    db_user = cursor.fetchone()
    
    if not db_user or not verifica_parola(form_data.password, db_user["parola_hash"]):
        raise HTTPException(status_code=401, detail="Email sau parola incorecta")
    
    token = creeaza_token({"sub": db_user["email"]})
    return {"access_token": token, "token_type": "bearer"}

# ---------------------------------------------------------------------------
# ULTIMA LINIE DIN FIȘIER - FĂRĂ EXCEPȚIE
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
