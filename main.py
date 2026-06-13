import os
import sqlite3
import jwt
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv  # NECESAR pentru .env

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # NECESAR pentru frontend
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Configurare (MODIFICAT pentru a citi din .env)
# ---------------------------------------------------------------------------
load_dotenv() 

DATABASE = os.environ.get("DATABASE_PATH", "sarcini.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "schimba-asta-in-productie")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
EXPIRARE_TOKEN_MINUTE = int(os.environ.get("EXPIRARE_TOKEN_MINUTE", 30))

context_parola = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
# Funcții utilitare
# ---------------------------------------------------------------------------

def hasheaza_parola(parola: str) -> str:
    return context_parola.hash(parola[:72])

def verifica_parola(parola: str, hash_parola: str) -> bool:
    return context_parola.verify(parola[:72], hash_parola)

def creeaza_token(date: dict) -> str:
    date_copie = date.copy()
    date_copie["exp"] = datetime.now(timezone.utc) + timedelta(minutes=EXPIRARE_TOKEN_MINUTE)
    return jwt.encode(date_copie, SECRET_KEY, algorithm=ALGORITHM)

def get_utilizator_curent(
    token: str = Depends(oauth2_schema),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token invalid.")
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalid.")

    utilizator = db.execute("SELECT * FROM utilizatori WHERE email = ?", (email,)).fetchone()
    if not utilizator:
        raise HTTPException(status_code=401, detail="Utilizatorul nu există.")
    return utilizator

# ---------------------------------------------------------------------------
# Endpoint-uri
# ---------------------------------------------------------------------------

@app.post("/inregistrare", status_code=201)
def inregistrare(utilizator: UtilizatorInregistrare, db: sqlite3.Connection = Depends(get_db)):
    existent = db.execute("SELECT id FROM utilizatori WHERE email = ?", (utilizator.email,)).fetchone()
    if existent:
        raise HTTPException(status_code=400, detail="Adresa de email este deja înregistrată.")

    db.execute(
        "INSERT INTO utilizatori (email, parola_hash) VALUES (?, ?)",
        (utilizator.email, hasheaza_parola(utilizator.parola)),
    )
    db.commit()
    return {"mesaj": "Utilizator creat cu succes."}

@app.post("/autentificare")
def autentificare(formular: OAuth2PasswordRequestForm = Depends(), db: sqlite3.Connection = Depends(get_db)):
    utilizator = db.execute("SELECT * FROM utilizatori WHERE email = ?", (formular.username,)).fetchone()
    if not utilizator or not verifica_parola(formular.password, utilizator["parola_hash"]):
        raise HTTPException(status_code=401, detail="Email sau parolă incorectă.")

    token = creeaza_token({"sub": utilizator["email"]})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/sarcini")
def obtine_sarcini(
    doar_nefinalizate: bool = False,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    query = "SELECT * FROM sarcini WHERE utilizator_id = ?"
    params = [utilizator_curent["id"]]
    if doar_nefinalizate:
        query += " AND finalizata = 0"
    sarcini = db.execute(query, params).fetchall()
    return [dict(s) for s in sarcini]

@app.post("/sarcini", status_code=201)
def creeaza_sarcina(
    sarcina: SarcinaCreare,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    cursor = db.execute(
        "INSERT INTO sarcini (titlu, descriere, utilizator_id) VALUES (?, ?, ?)",
        (sarcina.titlu, sarcina.descriere, utilizator_curent["id"]),
    )
    db.commit()
    return {"id": cursor.lastrowid, "titlu": sarcina.titlu}

@app.patch("/sarcini/{sarcina_id}/finalizeaza")
def finalizeaza_sarcina(
    sarcina_id: int,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    db.execute("UPDATE sarcini SET finalizata = 1 WHERE id = ? AND utilizator_id = ?", (sarcina_id, utilizator_curent["id"]))
    db.commit()
    return {"mesaj": "Sarcina finalizată."}

@app.delete("/sarcini/{sarcina_id}")
def sterge_sarcina(
    sarcina_id: int,
    db: sqlite3.Connection = Depends(get_db),
    utilizator_curent=Depends(get_utilizator_curent),
):
    db.execute("DELETE FROM sarcini WHERE id = ? AND utilizator_id = ?", (sarcina_id, utilizator_curent["id"]))
    db.commit()
    return {"mesaj": "Sarcina ștearsă."}

# ---------------------------------------------------------------------------
# Integrare Frontend (Static Files) - TREBUIE SĂ FIE ULTIMUL RÂND
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
