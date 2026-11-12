from tests.conftest import QueryMockConnection


def test_orders_health(orders_client):
    response = orders_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "orders_service", "status": "ok"}


def test_orders_docs(orders_client):
    response = orders_client.get("/docs")
    assert response.status_code == 200
    assert "Orders Service - Swagger UI" in response.text


def test_orders_openapi_json(orders_client):
    response = orders_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Orders Service"


def test_get_orders_empty(orders_module, orders_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchall_responses=[[]])
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.get("/")
    assert response.status_code == 200
    assert response.json() == []


def test_get_orders_with_data(orders_module, orders_client, monkeypatch):
    data = [
        {
            "id": 1,
            "user_id": 1,
            "user_name": "Alice",
            "book_id": 2,
            "book_title": "Dune",
            "quantity": 3,
            "created_at": "2026-06-22 18:00:00",
        }
    ]
    mock_conn = QueryMockConnection(fetchall_responses=[data])
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.get("/")
    assert response.status_code == 200
    assert response.json() == data


def test_get_order_found(orders_module, orders_client, monkeypatch):
    order = {
        "id": 1,
        "user_id": 1,
        "user_name": "Alice",
        "book_id": 2,
        "book_title": "Dune",
        "quantity": 3,
        "created_at": "2026-06-22 18:00:00",
    }
    mock_conn = QueryMockConnection(fetchone_responses=[order])
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.get("/1")
    assert response.status_code == 200
    assert response.json() == order


def test_get_order_not_found(orders_module, orders_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchone_responses=[None])
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.get("/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Orden no encontrada"


def test_create_order_success(orders_module, orders_client, monkeypatch):
    order_detail = {
        "id": 1,
        "user_id": 1,
        "user_name": "Alice",
        "book_id": 2,
        "book_title": "Dune",
        "quantity": 2,
        "created_at": "2026-06-22 18:00:00",
    }

    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return {"id": 1}
        if "SELECT id FROM books" in query:
            return {"id": 2}
        if "INSERT INTO orders" in query:
            return {"id": 1}
        if "FROM orders o" in query:
            return order_detail
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.post("/", json={"user_id": 1, "book_id": 2, "quantity": 2})
    assert response.status_code == 201
    assert response.json() == order_detail
    assert mock_conn.committed is True


def test_create_order_user_not_found(orders_module, orders_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return None
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.post("/", json={"user_id": 999, "book_id": 1, "quantity": 1})
    assert response.status_code == 404
    assert "el usuario no existe" in response.json()["detail"]


def test_create_order_book_not_found(orders_module, orders_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return {"id": 1}
        if "SELECT id FROM books" in query:
            return None
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.post("/", json={"user_id": 1, "book_id": 999, "quantity": 1})
    assert response.status_code == 404
    assert "el libro no existe" in response.json()["detail"]


def test_create_order_invalid_quantity(orders_client):
    response = orders_client.post("/", json={"user_id": 1, "book_id": 1, "quantity": 0})
    assert response.status_code == 422


def test_update_order_success(orders_module, orders_client, monkeypatch):
    updated_detail = {
        "id": 1,
        "user_id": 1,
        "user_name": "Alice",
        "book_id": 2,
        "book_title": "Dune",
        "quantity": 5,
        "created_at": "2026-06-22 18:00:00",
    }

    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return {"id": 1}
        if "SELECT id FROM books" in query:
            return {"id": 2}
        if "UPDATE orders" in query:
            return {"id": 1}
        if "FROM orders o" in query:
            return updated_detail
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.put("/1", json={"user_id": 1, "book_id": 2, "quantity": 5})
    assert response.status_code == 200
    assert response.json() == updated_detail
    assert mock_conn.committed is True


def test_update_order_not_found(orders_module, orders_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM users" in query:
            return {"id": 1}
        if "SELECT id FROM books" in query:
            return {"id": 2}
        if "UPDATE orders" in query:
            return None
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.put("/999", json={"user_id": 1, "book_id": 2, "quantity": 5})
    assert response.status_code == 404
    assert response.json()["detail"] == "Orden no encontrada"


def test_delete_order_success(orders_module, orders_client, monkeypatch):
    order_detail = {
        "id": 1,
        "user_id": 1,
        "user_name": "Alice",
        "book_id": 2,
        "book_title": "Dune",
        "quantity": 1,
        "created_at": "2026-06-22 18:00:00",
    }

    def custom_handler(query, params, fetch_type):
        if "FROM orders o" in query:
            return order_detail
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.delete("/1")
    assert response.status_code == 200
    assert response.json()["message"] == "Orden eliminada correctamente"
    assert mock_conn.committed is True


def test_delete_order_not_found(orders_module, orders_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchone_responses=[None])
    monkeypatch.setattr(orders_module, "get_connection", lambda: mock_conn)

    response = orders_client.delete("/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Orden no encontrada"
