from django.test import Client

from ribcage.hello.models import Message


def test_hello_world_renders_at_the_site_root(client, db):
    response = client.get("/")

    assert response.status_code == 200
    assert "Hello World" in response.text


def test_a_posted_message_is_shown_after_a_redirect(client, db):
    response = client.post("/", {"text": "Popcorn at seven"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert "Popcorn at seven" in client.get("/").text


def test_a_post_without_a_csrf_token_is_refused(db):
    browser = Client(enforce_csrf_checks=True)

    response = browser.post("/", {"text": "Forged"})

    assert response.status_code == 403
    assert "Forged" not in browser.get("/").text


def test_a_post_with_the_pages_csrf_token_is_accepted(db):
    browser = Client(enforce_csrf_checks=True)
    token = browser.get("/").context["csrf_token"]

    response = browser.post("/", {"text": "Genuine", "csrfmiddlewaretoken": token})

    assert response.status_code == 302


def test_only_the_last_20_messages_are_kept(client, db):
    for number in range(1, 22):
        client.post("/", {"text": f"Message {number:02}"})

    page = client.get("/").text

    assert "Message 01" not in page
    assert all(f"Message {number:02}" in page for number in range(2, 22))
    assert Message.objects.count() == 20


def test_messages_created_outside_the_form_are_trimmed_too(db):
    for number in range(25):
        Message.objects.create(text=f"Seeded {number}")

    assert Message.objects.count() == 20


def test_a_message_over_200_characters_is_refused(client, db):
    response = client.post("/", {"text": "x" * 201})

    assert response.status_code == 200
    assert "at most 200 characters" in response.text
    assert not Message.objects.exists()


def test_a_message_of_200_characters_is_accepted(client, db):
    response = client.post("/", {"text": "x" * 200})

    assert response.status_code == 302


def test_a_message_is_escaped_on_output(client, db):
    client.post("/", {"text": "<script>alert('hi')</script>"})

    page = client.get("/").text

    assert "<script>alert" not in page
    assert "&lt;script&gt;alert(&#x27;hi&#x27;)&lt;/script&gt;" in page


def test_an_empty_message_is_refused(client, db):
    response = client.post("/", {})

    assert response.status_code == 200
    assert "This field is required" in response.text


def test_the_page_lists_only_the_newest_20_messages_even_from_rows_that_skipped_trimming(client, db):
    Message.objects.bulk_create(Message(text=f"Bulk {number:02}") for number in range(25))

    page = client.get("/").text

    assert [number for number in range(25) if f"<li>Bulk {number:02}</li>" in page] == list(range(5, 25))
