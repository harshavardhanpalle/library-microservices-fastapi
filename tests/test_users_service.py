from tests.conftest import QueryMockConnection
import psycopg2


def test_users_health(users_client):
    response = users_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "users_service", "status": "ok"}


def test_users_docs(users_client):
    response = users_client.get("/docs")
    assert response.status_code == 200
    assert "Users Service - Swagger UI" in response.text


def test_users_openapi_json(users_client):
    response = users_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Users Service"


def test_get_users_empty(users_module, users_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchall_responses=[[]])
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.get("/")
    assert response.status_code == 200
    assert response.json() == []


def test_get_users_with_data(users_module, users_client, monkeypatch):
    data = [
        {"id": 1, "name": "Alice Smith", "email": "alice@example.com"},
        {"id": 2, "name": "Bob Jones", "email": "bob@example.com"},
    ]
    mock_conn = QueryMockConnection(fetchall_responses=[data])
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.get("/")
    assert response.status_code == 200
    assert response.json() == data


def test_get_user_found(users_module, users_client, monkeypatch):
    data = {"id": 1, "name": "Alice Smith", "email": "alice@example.com"}
    mock_conn = QueryMockConnection(fetchone_responses=[data])
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.get("/1")
    assert response.status_code == 200
    assert response.json() == data


def test_get_user_not_found(users_module, users_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchone_responses=[None])
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.get("/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_create_user_success(users_module, users_client, monkeypatch):
    created = {"id": 1, "name": "Charlie Brown", "email": "charlie@example.com"}
    mock_conn = QueryMockConnection(fetchone_responses=[created])
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.post("/", json={"name": "Charlie Brown", "email": "charlie@example.com"})
    assert response.status_code == 201
    assert response.json() == created
    assert mock_conn.committed is True


def test_create_user_validation_error(users_client):
    response = users_client.post("/", json={"name": "Invalid", "email": "not-an-email"})
    assert response.status_code == 422


def test_create_user_duplicate_email(users_module, users_client, monkeypatch):
    class DuplicateEmailConnection(QueryMockConnection):
        def cursor(self, cursor_factory=None):
            class ErrorCursor:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass

                def execute(self, query, params=None):
                    raise psycopg2.IntegrityError("duplicate key value violates unique constraint")

            return ErrorCursor()

    mock_conn = DuplicateEmailConnection()
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.post("/", json={"name": "Duplicate", "email": "existing@example.com"})
    assert response.status_code == 409
    assert "El email ya existe" in response.json()["detail"]


def test_update_user_success(users_module, users_client, monkeypatch):
    updated = {"id": 1, "name": "Alice Updated", "email": "alice.updated@example.com"}
    mock_conn = QueryMockConnection(fetchone_responses=[updated])
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.put("/1", json={"name": "Alice Updated", "email": "alice.updated@example.com"})
    assert response.status_code == 200
    assert response.json() == updated
    assert mock_conn.committed is True


def test_update_user_not_found(users_module, users_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchone_responses=[None])
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.put("/999", json={"name": "Ghost", "email": "ghost@example.com"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_delete_user_success(users_module, users_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return {"id": 1}
        if "to_regclass" in query:
            return {"table_name": "orders"}
        if "COUNT(*) AS total" in query:
            return {"total": 0}
        if "DELETE FROM users" in query:
            return {"id": 1, "name": "Alice", "email": "alice@example.com"}
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.delete("/1")
    assert response.status_code == 200
    assert response.json()["message"] == "Usuario eliminado correctamente"


def test_delete_user_not_found(users_module, users_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return None
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.delete("/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no encontrado"


def test_delete_user_conflict_with_orders(users_module, users_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return {"id": 1}
        if "to_regclass" in query:
            return {"table_name": "orders"}
        if "COUNT(*) AS total" in query:
            return {"total": 2}
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(users_module, "get_connection", lambda: mock_conn)

    response = users_client.delete("/1")
    assert response.status_code == 409
    assert "tiene órdenes asociadas" in response.json()["detail"]
