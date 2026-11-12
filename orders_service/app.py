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


class OrderCreate(BaseModel):
    user_id: int = Field(..., gt=0)
    book_id: int = Field(..., gt=0)
    quantity: int = Field(default=1, gt=0)


class OrderUpdate(BaseModel):
    user_id: int = Field(..., gt=0)
    book_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


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
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

        conn.commit()
    finally:
        conn.close()


def validate_user_and_book(conn, user_id: int, book_id: int):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM users WHERE id = %s;", (user_id,))
        user = cur.fetchone()

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="No se puede procesar la orden porque el usuario no existe"
            )

        cur.execute("SELECT id FROM books WHERE id = %s;", (book_id,))
        book = cur.fetchone()

        if book is None:
            raise HTTPException(
                status_code=404,
                detail="No se puede procesar la orden porque el libro no existe"
            )


def get_order_detail(conn, order_id: int):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                o.id,
                o.user_id,
                u.name AS user_name,
                o.book_id,
                b.title AS book_title,
                o.quantity,
                TO_CHAR(o.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            LEFT JOIN books b ON b.id = o.book_id
            WHERE o.id = %s;
        """, (order_id,))

        return cur.fetchone()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("SKIP_DB_INIT", "false").lower() != "true":
        init_db()
    yield


app = FastAPI(
    title="Orders Service",
    description="Microservicio CRUD para la gestión de órdenes.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    servers=[
        {"url": "/api/orders"}
    ],
    lifespan=lifespan,
)


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title="Orders Service - Swagger UI"
    )


@app.get("/health")
def health():
    return {
        "service": "orders_service",
        "status": "ok"
    }


@app.get("/")
def get_orders():
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    o.id,
                    o.user_id,
                    u.name AS user_name,
                    o.book_id,
                    b.title AS book_title,
                    o.quantity,
                    TO_CHAR(o.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
                FROM orders o
                LEFT JOIN users u ON u.id = o.user_id
                LEFT JOIN books b ON b.id = o.book_id
                ORDER BY o.id;
            """)
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/{order_id}")
def get_order(order_id: int):
    conn = get_connection()

    try:
        order = get_order_detail(conn, order_id)

        if order is None:
            raise HTTPException(status_code=404, detail="Orden no encontrada")

        return order
    finally:
        conn.close()


@app.post("/", status_code=201)
def create_order(order: OrderCreate):
    conn = get_connection()

    try:
        validate_user_and_book(conn, order.user_id, order.book_id)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO orders (user_id, book_id, quantity)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (order.user_id, order.book_id, order.quantity))

            created_order_id = cur.fetchone()["id"]

        created_order = get_order_detail(conn, created_order_id)

        conn.commit()
        return created_order

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.put("/{order_id}")
def update_order(order_id: int, order: OrderUpdate):
    conn = get_connection()

    try:
        validate_user_and_book(conn, order.user_id, order.book_id)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE orders
                SET user_id = %s,
                    book_id = %s,
                    quantity = %s
                WHERE id = %s
                RETURNING id;
            """, (order.user_id, order.book_id, order.quantity, order_id))

            updated = cur.fetchone()

        if updated is None:
            raise HTTPException(status_code=404, detail="Orden no encontrada")

        updated_order = get_order_detail(conn, order_id)

        conn.commit()
        return updated_order

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.delete("/{order_id}")
def delete_order(order_id: int):
    conn = get_connection()

    try:
        existing_order = get_order_detail(conn, order_id)

        if existing_order is None:
            raise HTTPException(status_code=404, detail="Orden no encontrada")

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM orders WHERE id = %s;", (order_id,))

        conn.commit()
        return {
            "message": "Orden eliminada correctamente",
            "order": existing_order
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
