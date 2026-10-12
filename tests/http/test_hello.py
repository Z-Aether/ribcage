def test_hello_world_renders_at_the_site_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Hello World" in response.text
