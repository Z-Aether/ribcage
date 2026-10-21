from django.urls import path

from ribcage.console.views import console, films_tab, phase_tab, pick_tab, roster_tab
from ribcage.gallery.views import gallery
from ribcage.identity.views import (
    admin_login,
    admin_logout,
    change_password,
    join,
    join_details,
    login,
    logout,
    password_changed,
)
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
    path("console/", console, name="console"),
    path("console/phase/", phase_tab, name="console_phase"),
    path("console/films/", films_tab, name="console_films"),
    path("console/pick/", pick_tab, name="console_pick"),
    path("console/roster/", roster_tab, name="console_roster"),
    path("console/login/", admin_login, name="admin_login"),
    path("console/logout/", admin_logout, name="admin_logout"),
]
