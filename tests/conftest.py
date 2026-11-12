import importlib.util
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Configure test environment before any app import
os.environ["SKIP_DB_INIT"] = "true"
os.environ["DB_MAX_RETRIES"] = "1"
os.environ["DB_RETRY_DELAY"] = "0"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "test_db"
os.environ["POSTGRES_USER"] = "test_user"
os.environ["POSTGRES_PASSWORD"] = "test_password"

# Add microservices paths to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for svc in ["books_service", "users_service", "orders_service"]:
    p = os.path.join(root_dir, svc)
    if p not in sys.path:
        sys.path.insert(0, p)


def load_service_app(service_folder: str):
    module_path = os.path.join(root_dir, service_folder, "app.py")
    spec = importlib.util.spec_from_file_location(f"{service_folder}_app", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def books_module():
    return load_service_app("books_service")


@pytest.fixture(scope="session")
def users_module():
    return load_service_app("users_service")


@pytest.fixture(scope="session")
def orders_module():
    return load_service_app("orders_service")


@pytest.fixture
def books_client(books_module):
    return TestClient(books_module.app)


@pytest.fixture
def users_client(users_module):
    return TestClient(users_module.app)


@pytest.fixture
def orders_client(orders_module):
    return TestClient(orders_module.app)


class QueryMockConnection:
    def __init__(self, fetchone_responses=None, fetchall_responses=None, custom_handler=None):
        self.fetchone_responses = list(fetchone_responses or [])
        self.fetchall_responses = list(fetchall_responses or [])
        self.custom_handler = custom_handler
        self.queries = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return QueryMockCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class QueryMockCursor:
    def __init__(self, connection):
        self.conn = connection
        self.last_query = None
        self.last_params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        self.conn.queries.append((query, params))

    def fetchone(self):
        if self.conn.custom_handler:
            res = self.conn.custom_handler(self.last_query, self.last_params, "fetchone")
            if res is not None:
                return res
        if self.conn.fetchone_responses:
            return self.conn.fetchone_responses.pop(0)
        return None

    def fetchall(self):
        if self.conn.custom_handler:
            res = self.conn.custom_handler(self.last_query, self.last_params, "fetchall")
            if res is not None:
                return res
        if self.conn.fetchall_responses:
            return self.conn.fetchall_responses.pop(0)
        return []
