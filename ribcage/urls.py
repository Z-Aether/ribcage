from django.urls import path

from ribcage.gallery.views import gallery
from ribcage.identity.views import home, join, join_details, login, logout
from ribcage.privacy import privacy_policy

urlpatterns = [
    path("", home, name="home"),
    path("login/", login, name="login"),
    path("join/", join, name="join"),
    path("join/details/", join_details, name="join_details"),
    path("logout/", logout, name="logout"),
    path("privacy/", privacy_policy, name="privacy"),
    path("gallery/", gallery, name="gallery"),
]
