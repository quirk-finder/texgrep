from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health_view, name="health"),
    path("search", views.search_view, name="search"),
    path("reindex", views.reindex_view, name="reindex"),
]
