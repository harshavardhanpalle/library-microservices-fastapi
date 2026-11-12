import os


def test_nginx_configuration():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    nginx_path = os.path.join(root_dir, "nginx", "nginx.conf")
    assert os.path.exists(nginx_path), "nginx/nginx.conf must exist"

    with open(nginx_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify security directive
    assert "server_tokens off;" in content

    # Verify upstream definitions
    assert "upstream books_backend" in content
    assert "server books_service:5000;" in content
    assert "upstream users_backend" in content
    assert "server users_service:5000;" in content
    assert "upstream orders_backend" in content
    assert "server orders_service:5000;" in content

    # Verify routing and prefix propagation
    assert "location /api/books/" in content
    assert "proxy_set_header X-Forwarded-Prefix /api/books;" in content

    assert "location /api/users/" in content
    assert "proxy_set_header X-Forwarded-Prefix /api/users;" in content

    assert "location /api/orders/" in content
    assert "proxy_set_header X-Forwarded-Prefix /api/orders;" in content
