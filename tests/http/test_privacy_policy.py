from ribcage import privacy


def test_the_privacy_policy_is_reachable_without_logging_in(client):
    response = client.get("/privacy/")

    assert response.status_code == 200
    assert "<h1>Privacy policy</h1>" in response.text


def test_the_page_is_rendered_from_the_policy_file_as_markdown(client, tmp_path, monkeypatch):
    policy = tmp_path / "policy.md"
    policy.write_text("# A stand-in policy\n\nKept *only* in this file.\n", encoding="utf-8")
    monkeypatch.setattr(privacy, "POLICY_FILE", policy)

    page = client.get("/privacy/").text

    assert "<h1>A stand-in policy</h1>" in page
    assert "<p>Kept <em>only</em> in this file.</p>" in page


def test_the_hello_world_page_links_the_privacy_policy(client, db):
    page = client.get("/").text

    assert '<a href="/privacy/">Privacy policy</a>' in page


def test_the_page_extends_the_base_template(client):
    response = client.get("/privacy/")

    assert "base.html" in [template.name for template in response.templates]
