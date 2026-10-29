import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_check(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["app_name"].lower() == "impervia"
    assert data["database"] == "healthy"


def test_public_privacy_analyze(client: TestClient):
    # Public analyze without auth
    response = client.post(
        "/api/v1/privacy/analyze",
        json={"text": "Can you explain Dijkstra's algorithm? My email is alice@univ.edu."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pii_detected"] is True
    assert data["processing_path"] == "sanitize"
    assert "[REDACTED_EMAIL]" in data["sanitized_text"]
    assert "alice@univ.edu" not in data["sanitized_text"]
    assert len(data["findings"]) == 1
    assert data["findings"][0]["category"] == "email"


def test_auth_registration_and_login_flow(client: TestClient):
    unique_email = f"student_{uuid.uuid4().hex[:8]}@university.edu"
    password = "SecurePassword123!"

    # 1. Register
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": password, "name": "Student Test"},
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert reg_data["user"]["email"] == unique_email
    # Verify default privacy settings created
    assert reg_data["settings"]["save_chat_history"] is False
    assert reg_data["settings"]["allow_aggregate_analytics"] is False

    # 2. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Get profile (/auth/me)
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == unique_email

    # 4. Get settings
    settings_resp = client.get("/api/v1/settings", headers=headers)
    assert settings_resp.status_code == 200
    assert settings_resp.json()["save_chat_history"] is False

    # 5. Update settings: enable save_chat_history and analytics
    update_resp = client.put(
        "/api/v1/settings",
        json={"save_chat_history": True, "allow_aggregate_analytics": True},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["save_chat_history"] is True
    assert update_resp.json()["allow_aggregate_analytics"] is True

    # 6. Process message in chat with save_chat_history=True
    chat_resp = client.post(
        "/api/v1/chat/process",
        json={"message": "Can you explain binary search trees?"},
        headers=headers,
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["user_message_stored"] is True
    assert chat_data["user_message_id"] is not None
    assert chat_data["session_id"] is not None
    assert chat_data["processing_path"] == "pass_through"

    # 7. Check user analyses list
    analyses_resp = client.get("/api/v1/privacy/analyses", headers=headers)
    assert analyses_resp.status_code == 200
    analyses_list = analyses_resp.json()
    assert len(analyses_list) >= 1

    # 8. Delete user account
    del_resp = client.delete("/api/v1/auth/account", headers=headers)
    assert del_resp.status_code == 200

    # 9. Verify user is now deleted (login fails)
    relogin_resp = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert relogin_resp.status_code == 401
