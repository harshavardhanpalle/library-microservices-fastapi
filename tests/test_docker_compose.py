import os
import yaml


def test_docker_compose_structure():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    compose_path = os.path.join(root_dir, "docker-compose.yml")
    assert os.path.exists(compose_path), "docker-compose.yml must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    assert "services" in compose
    services = compose["services"]

    # Verify all expected services exist
    expected_services = ["db", "books_service", "users_service", "orders_service", "nginx"]
    for svc in expected_services:
        assert svc in services, f"Missing service: {svc}"

    # Verify DB healthcheck
    assert "healthcheck" in services["db"]
    assert "pg_isready" in " ".join(services["db"]["healthcheck"]["test"])

    # Verify security hardening on app services
    for svc in ["books_service", "users_service", "orders_service"]:
        svc_conf = services[svc]
        assert svc_conf.get("read_only") is True, f"{svc} must be read_only"
        assert "ALL" in svc_conf.get("cap_drop", []), f"{svc} must drop ALL caps"
        assert "no-new-privileges:true" in svc_conf.get("security_opt", []), f"{svc} must enforce no-new-privileges"

    # Verify networks
    assert "networks" in compose
    networks = compose["networks"]
    assert "public_net" in networks
    assert "app_net" in networks
    assert "db_net" in networks
    assert networks["app_net"].get("internal") is True
    assert networks["db_net"].get("internal") is True

    # Verify persistent volume
    assert "volumes" in compose
    assert "postgres_data" in compose["volumes"]
