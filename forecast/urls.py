from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/health/", views.health, name="health"),
    path("api/predict/", views.predict, name="predict"),
    path("api/live/", views.live, name="live"),
    path("api/forecast/", views.forecast, name="forecast"),
]
