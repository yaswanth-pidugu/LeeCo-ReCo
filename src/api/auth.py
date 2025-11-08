# src/api/auth.py
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional, Dict
from src.database.db_config import get_db_connection


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))


router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class SignupRequest(BaseModel):
    username: constr(strip_whitespace=True, min_length=3, max_length=30)
    email: EmailStr
    password: constr(min_length=8, max_length=128)

    @validator("username")
    def no_spaces_username(cls, v):
        if " " in v:
            raise ValueError("username must not contain spaces")
        return v

    @validator("password")
    def strong_password(cls, v):
        # require at least one uppercase, one lowercase, one digit
        if not re.search(r"[A-Z]", v):
            raise ValueError("password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("password must contain at least one digit")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int

def _hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.utcnow()
    to_encode.update({"iat": now})
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

@router.post("/signup")
def signup(req: SignupRequest):
    """
    Register a new user with hashed password.
    Enforces unique username and email.
    """
    conn = get_db_connection()
    if isinstance(conn, dict) and "error" in conn:
        raise HTTPException(status_code=500, detail=conn["error"])

    try:
        username = req.username.strip()
        email = req.email.strip().lower()
        password = req.password

        cursor = conn.cursor(dictionary=True)

        # check uniqueness
        cursor.execute(
            "SELECT id FROM users WHERE username = %s OR email = %s LIMIT 1",
            (username, email),
        )
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username or email already exists")

        hashed = _hash_password(password)

        cursor.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)",
            (username, email, hashed),
        )
        conn.commit()

        return {"message": "User registered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user (username or email) and issue JWT token.
    Accepts OAuth2PasswordRequestForm (fields: username, password).
    """
    conn = get_db_connection()
    if isinstance(conn, dict) and "error" in conn:
        raise HTTPException(status_code=500, detail=conn["error"])

    try:
        identifier = form_data.username.strip()  # could be username or email
        password = form_data.password

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, email, password_hash FROM users WHERE username = %s OR email = %s LIMIT 1",
            (identifier, identifier),
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

        stored_hash = user.get("password_hash") or ""
        if not _verify_password(password, stored_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

        token_payload = {
            "sub": user["username"],
            "user_id": int(user["id"]),
            "email": user["email"],
        }
        access_token = _create_access_token(token_payload, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

        return {"access_token": access_token, "token_type": "bearer", "user_id": int(user["id"])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Verify token and return user record dict {id, username, email}.
    """
    conn = get_db_connection()
    if isinstance(conn, dict) and "error" in conn:
        raise HTTPException(status_code=500, detail=conn["error"])

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        username = payload.get("sub")
        if not user_id or not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@router.get("/me")
def read_current_user(current_user: dict = Depends(get_current_user)):
    """Return user info from verified token."""
    return {"user": current_user}


def verify_token(token: str = Depends(oauth2_scheme)):
    """Lightweight JWT verifier (returns payload if valid)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
