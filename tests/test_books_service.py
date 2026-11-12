from tests.conftest import QueryMockConnection


def test_books_health(books_client):
    response = books_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "books_service", "status": "ok"}


def test_books_docs(books_client):
    response = books_client.get("/docs")
    assert response.status_code == 200
    assert "Books Service - Swagger UI" in response.text


def test_books_openapi_json(books_client):
    response = books_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Books Service"


def test_get_books_empty(books_module, books_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchall_responses=[[]])
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.get("/")
    assert response.status_code == 200
    assert response.json() == []
    assert mock_conn.closed is True


def test_get_books_with_data(books_module, books_client, monkeypatch):
    data = [
        {"id": 1, "title": "1984", "author": "George Orwell"},
        {"id": 2, "title": "Fahrenheit 451", "author": "Ray Bradbury"},
    ]
    mock_conn = QueryMockConnection(fetchall_responses=[data])
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.get("/")
    assert response.status_code == 200
    assert response.json() == data


def test_get_book_found(books_module, books_client, monkeypatch):
    data = {"id": 1, "title": "1984", "author": "George Orwell"}
    mock_conn = QueryMockConnection(fetchone_responses=[data])
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.get("/1")
    assert response.status_code == 200
    assert response.json() == data


def test_get_book_not_found(books_module, books_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchone_responses=[None])
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.get("/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Libro no encontrado"


def test_create_book_success(books_module, books_client, monkeypatch):
    created = {"id": 1, "title": "Dune", "author": "Frank Herbert"}
    mock_conn = QueryMockConnection(fetchone_responses=[created])
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.post("/", json={"title": "Dune", "author": "Frank Herbert"})
    assert response.status_code == 201
    assert response.json() == created
    assert mock_conn.committed is True


def test_create_book_validation_error(books_client):
    response = books_client.post("/", json={"title": ""})
    assert response.status_code == 422


def test_update_book_success(books_module, books_client, monkeypatch):
    updated = {"id": 1, "title": "Dune Messiah", "author": "Frank Herbert"}
    mock_conn = QueryMockConnection(fetchone_responses=[updated])
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.put("/1", json={"title": "Dune Messiah", "author": "Frank Herbert"})
    assert response.status_code == 200
    assert response.json() == updated
    assert mock_conn.committed is True


def test_update_book_not_found(books_module, books_client, monkeypatch):
    mock_conn = QueryMockConnection(fetchone_responses=[None])
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.put("/999", json={"title": "Non-existent", "author": "Unknown"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Libro no encontrado"
    assert mock_conn.rolled_back is True


def test_delete_book_success(books_module, books_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM books" in query:
            return {"id": 1}
        if "to_regclass" in query:
            return {"table_name": "orders"}
        if "COUNT(*) AS total" in query:
            return {"total": 0}
        if "DELETE FROM books" in query:
            return {"id": 1, "title": "Dune", "author": "Frank Herbert"}
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.delete("/1")
    assert response.status_code == 200
    assert response.json()["message"] == "Libro eliminado correctamente"
    assert mock_conn.committed is True


def test_delete_book_not_found(books_module, books_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM books" in query:
            return None
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.delete("/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Libro no encontrado"


def test_delete_book_conflict_with_orders(books_module, books_client, monkeypatch):
    def custom_handler(query, params, fetch_type):
        if "SELECT id FROM books" in query:
            return {"id": 1}
        if "to_regclass" in query:
            return {"table_name": "orders"}
        if "COUNT(*) AS total" in query:
            return {"total": 3}
        return None

    mock_conn = QueryMockConnection(custom_handler=custom_handler)
    monkeypatch.setattr(books_module, "get_connection", lambda: mock_conn)

    response = books_client.delete("/1")
    assert response.status_code == 409
    assert "tiene órdenes asociadas" in response.json()["detail"]
