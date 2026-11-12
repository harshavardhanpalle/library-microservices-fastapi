from contextlib import asynccontextmanager
import os
import time

import psycopg2
from psycopg2 import OperationalError, IntegrityError
from psycopg2.extras import RealDictCursor

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fastapi.openapi.docs import get_swagger_ui_html


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB", "library_db"),
    "user": os.getenv("POSTGRES_USER", "library_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "library_password_secure123"),
}


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_connection():
    max_retries = int(os.getenv("DB_MAX_RETRIES", "10"))
    retry_delay = float(os.getenv("DB_RETRY_DELAY", "3"))

    for attempt in range(max_retries):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except OperationalError:
            if attempt == max_retries - 1:
                raise
            print(f"Esperando a PostgreSQL... ({attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

    raise Exception("No se pudo conectar a PostgreSQL")


def table_exists(conn, table_name: str) -> bool:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT to_regclass(%s) AS table_name;", (table_name,))
        result = cur.fetchone()

    return result["table_name"] is not None


def init_db():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    email VARCHAR(160) UNIQUE NOT NULL
                );
            """)

        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("SKIP_DB_INIT", "false").lower() != "true":
        init_db()
    yield


app = FastAPI(
    title="Users Service",
    description="Microservicio CRUD para la gestión de usuarios.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    servers=[
        {"url": "/api/users"}
    ],
    lifespan=lifespan,
)


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title="Users Service - Swagger UI"
    )


@app.get("/health")
def health():
    return {
        "service": "users_service",
        "status": "ok"
    }


@app.get("/")
def get_users():
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name, email FROM users ORDER BY id;")
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/{user_id}")
def get_user(user_id: int):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, email FROM users WHERE id = %s;",
                (user_id,)
            )
            user = cur.fetchone()

        if user is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return user
    finally:
        conn.close()


@app.post("/", status_code=201)
def create_user(user: UserCreate):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO users (name, email)
                VALUES (%s, %s)
                RETURNING id, name, email;
            """, (user.name, user.email))

            created_user = cur.fetchone()

        conn.commit()
        return created_user

    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="El email ya existe") from None

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.put("/{user_id}")
def update_user(user_id: int, user: UserUpdate):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE users
                SET name = %s,
                    email = %s
                WHERE id = %s
                RETURNING id, name, email;
            """, (user.name, user.email, user_id))

            updated_user = cur.fetchone()

        if updated_user is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        conn.commit()
        return updated_user

    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="El email ya existe") from None

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.delete("/{user_id}")
def delete_user(user_id: int):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE id = %s;", (user_id,))
            existing_user = cur.fetchone()

            if existing_user is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            if table_exists(conn, "orders"):
                cur.execute("SELECT COUNT(*) AS total FROM orders WHERE user_id = %s;", (user_id,))
                total_orders = cur.fetchone()["total"]

                if total_orders > 0:
                    raise HTTPException(
                        status_code=409,
                        detail="No se puede eliminar el usuario porque tiene órdenes asociadas"
                    )

            cur.execute(
                "DELETE FROM users WHERE id = %s RETURNING id, name, email;",
                (user_id,)
            )
            deleted_user = cur.fetchone()

        conn.commit()
        return {
            "message": "Usuario eliminado correctamente",
            "user": deleted_user
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
