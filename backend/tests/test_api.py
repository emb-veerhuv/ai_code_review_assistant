from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.json()["status"] == "ok"


def test_repository_upload():
    data = BytesIO()
    with ZipFile(data, "w") as z:
        z.writestr("src/good_file.cpp", "class bad_name { };\nvoid f(){ new int; }")
    data.seek(0)
    with TestClient(app) as client:
        response = client.post("/api/review/repository", files={"repository": ("repo.zip", data.getvalue(), "application/zip")})
        assert response.status_code == 200
        body = response.json()
        ids = {x["rule_id"] for x in body["findings"]}
        assert "C-001" in ids and "NAME-001" in ids
