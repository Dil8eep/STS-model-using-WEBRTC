from django.urls import path

from .views import webrtc_offer


urlpatterns = [
    path("offer/", webrtc_offer, name="webrtc_offer"),
]
