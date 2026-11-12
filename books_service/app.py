from contextlib import asynccontextmanager
import os
import time

import psycopg2
from psycopg2 import OperationalError
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


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    author: str = Field(..., min_length=1, max_length=120)


class BookUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    author: str = Field(..., min_length=1, max_length=120)


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
                CREATE TABLE IF NOT EXISTS books (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(120) NOT NULL,
                    author VARCHAR(120) NOT NULL
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
    title="Books Service",
    description="Microservicio CRUD para la gestión de libros.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    servers=[
        {"url": "/api/books"}
    ],
    lifespan=lifespan,
)


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title="Books Service - Swagger UI"
    )


@app.get("/health")
def health():
    return {
        "service": "books_service",
        "status": "ok"
    }


@app.get("/")
def get_books():
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, title, author FROM books ORDER BY id;")
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/{book_id}")
def get_book(book_id: int):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title, author FROM books WHERE id = %s;",
                (book_id,)
            )
            book = cur.fetchone()

        if book is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")

        return book
    finally:
        conn.close()


@app.post("/", status_code=201)
def create_book(book: BookCreate):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO books (title, author)
                VALUES (%s, %s)
                RETURNING id, title, author;
            """, (book.title, book.author))

            created_book = cur.fetchone()

        conn.commit()
        return created_book

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.put("/{book_id}")
def update_book(book_id: int, book: BookUpdate):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE books
                SET title = %s,
                    author = %s
                WHERE id = %s
                RETURNING id, title, author;
            """, (book.title, book.author, book_id))

            updated_book = cur.fetchone()

        if updated_book is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")

        conn.commit()
        return updated_book

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.delete("/{book_id}")
def delete_book(book_id: int):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM books WHERE id = %s;", (book_id,))
            existing_book = cur.fetchone()

            if existing_book is None:
                raise HTTPException(status_code=404, detail="Libro no encontrado")

            if table_exists(conn, "orders"):
                cur.execute("SELECT COUNT(*) AS total FROM orders WHERE book_id = %s;", (book_id,))
                total_orders = cur.fetchone()["total"]

                if total_orders > 0:
                    raise HTTPException(
                        status_code=409,
                        detail="No se puede eliminar el libro porque tiene órdenes asociadas"
                    )

            cur.execute(
                "DELETE FROM books WHERE id = %s RETURNING id, title, author;",
                (book_id,)
            )
            deleted_book = cur.fetchone()

        conn.commit()
        return {
            "message": "Libro eliminado correctamente",
            "book": deleted_book
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
