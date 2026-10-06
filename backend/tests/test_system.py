def test_health(client):
    response = client.get("/api/system/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_learning_settings_defaults(client):
    response = client.get("/api/system/settings")
    assert response.status_code == 200
    assert response.json() == {"mastery_streak": 5, "daily_vocab_count": 5}
