from __future__ import annotations

import os
import sys
import types

import django
from django.core.cache import cache
from django.http import JsonResponse
from django.test import Client, override_settings
from django.urls import path

from search.ratelimit import ratelimit

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "texgrep.settings")
django.setup()


def test_ratelimit_blocks_after_threshold() -> None:
    cache.clear()
    client = Client()

    @ratelimit(key="ip", rate="1/m", block=True)
    def limited_view(request):
        return JsonResponse({"message": "ok"})

    module_name = "tests.test_ratelimit_urls"
    urlconf = types.ModuleType(module_name)
    urlconf.urlpatterns = [path("limited/", limited_view)]
    sys.modules[module_name] = urlconf

    try:
        with override_settings(ROOT_URLCONF=module_name):
            first = client.get("/limited/", REMOTE_ADDR="127.0.0.1")
            assert first.status_code == 200
            assert first.json() == {"message": "ok"}

            second = client.get("/limited/", REMOTE_ADDR="127.0.0.1")
            assert second.status_code == 429
            assert second.json() == {"detail": "Too many requests"}
    finally:
        sys.modules.pop(module_name, None)
        cache.clear()
