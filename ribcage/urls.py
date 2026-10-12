from django.urls import path

from ribcage.hello.views import hello

urlpatterns = [
    path("", hello, name="hello"),
]
