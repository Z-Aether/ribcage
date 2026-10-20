from django.urls import path

from ribcage.gallery.views import gallery
from ribcage.hello.views import hello
from ribcage.privacy import privacy_policy

urlpatterns = [
    path("", hello, name="hello"),
    path("privacy/", privacy_policy, name="privacy"),
    path("gallery/", gallery, name="gallery"),
]
