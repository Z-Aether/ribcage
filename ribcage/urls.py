from django.urls import path

from ribcage.gallery.views import gallery
from ribcage.identity.views import change_password, join, join_details, login, logout, password_changed
from ribcage.phase.views import phase_page, welcome
from ribcage.privacy import privacy_policy

urlpatterns = [
    path("", phase_page, name="phase_page"),
    path("welcome/", welcome, name="welcome"),
    path("login/", login, name="login"),
    path("join/", join, name="join"),
    path("join/details/", join_details, name="join_details"),
    path("logout/", logout, name="logout"),
    path("password/", change_password, name="change_password"),
    path("password/changed/", password_changed, name="password_changed"),
    path("privacy/", privacy_policy, name="privacy"),
    path("gallery/", gallery, name="gallery"),
]
