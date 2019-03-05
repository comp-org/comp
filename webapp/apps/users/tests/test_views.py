import pytest

from django.contrib import auth

User = auth.get_user_model()


@pytest.mark.django_db
class TestUsersViews:
    def test_get_login(self, client):
        resp = client.get("/users/signup/")
        assert resp.status_code == 200

    def test_post_login(self, client, password):
        data = {
            "csrfmiddlewaretoken": ["abc123"],
            "username": ["tester"],
            "email": ["tester@testing.ai"],
            "password1": [password],
            "password2": [password],
            "stripeToken": ["tok_bypassPending"],
        }

        resp = client.post("/users/signup/", data=data)
        assert resp.status_code == 302

        user = User.objects.get(username="tester")
        assert user
        # assert user.customer
        assert user.profile
        assert user.profile.is_active

    @pytest.mark.requires_stripe
    def test_post_login_w_customer(self, client, password):
        data = {
            "csrfmiddlewaretoken": ["abc123"],
            "username": ["tester"],
            "email": ["tester@testing.ai"],
            "password1": [password],
            "password2": [password],
            "stripeToken": ["tok_bypassPending"],
        }

        resp = client.post("/users/signup/", data=data)
        assert resp.status_code == 302

        user = User.objects.get(username="tester")
        assert user
        assert user.customer
        assert user.profile
        assert user.profile.is_active

    def test_get_user_settings(self, client, profile, password):
        success = client.login(username=profile.user.username, password=password)
        assert success
        resp = client.get("/users/settings/")
        assert resp.status_code == 200

    def test_get_user_profile(
        self, monkeypatch, client, profile, password, test_models
    ):
        monkeypatch.setattr("webapp.apps.users.models.reverse", lambda x: "/url/")
        success = client.login(username=profile.user.username, password=password)
        assert success
        resp = client.get(f"/{profile.user.username}/")
        assert resp.status_code == 200

    def test_get_user_no_access(self, client, profile, password):
        resp = client.get(f"/tester/")
        assert resp.status_code == 200

    def test_get_user_does_not_exist(self, client, profile, password):
        resp = client.get(f"/notarealuser/")
        assert resp.status_code == 404

    def test_change_password(self, client, profile, password):
        success = client.login(username=profile.user.username, password=password)
        assert success

        resp = client.get("/users/password_change/")
        assert resp.status_code == 200

        data = {
            "old_password": password,
            "new_password1": "newpassyo1",
            "new_password2": "newpassyo1",
        }

        resp = client.post("/users/password_change/", data=data)
        assert resp.status_code == 302
        assert resp.url == "/users/password_change/done/"

        resp = client.get("/users/password_change/done/")
        assert resp.status_code == 200

    def test_cancel_subscriptions(self, client, profile, password):
        success = client.login(username=profile.user.username, password=password)
        assert success

        resp = client.get("/users/cancel/")
        assert resp.status_code == 200
        data = {"confirm_username": profile.user.username}
        resp = client.post("/users/cancel/", data=data)
        assert resp.status_code == 302
        assert resp.url == "/users/cancel/done/"

        resp = client.get(resp.url)
        assert resp.status_code == 200

    def test_delete_user(self, client, profile, password):
        success = client.login(username=profile.user.username, password=password)
        assert success

        resp = client.get("/users/delete/")
        assert resp.status_code == 200
        data = {"confirm_username": profile.user.username}
        resp = client.post("/users/delete/", data=data)
        assert resp.status_code == 302
        assert resp.url == "/users/delete/done/"

        resp = client.get(resp.url)
        assert resp.status_code == 200
        user = auth.get_user(client)
        assert not user.is_authenticated

    def test_access_to_profile_pages(self, client):
        user = auth.get_user(client)
        assert not user.is_authenticated
        restricted = [
            "/users/settings/",
            "/users/password_change/",
            "/users/password_change/done/",
            "/billing/update/",
            "/billing/update/done/",
            "/users/cancel/",
            "/users/cancel/done/",
            "/users/delete/",
        ]
        for url in restricted:
            resp = client.get(url)
            assert resp.status_code == 302
            assert resp.url.startswith("/users/login/")
