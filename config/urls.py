from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse, HttpResponse

def manifest_view(request):
    return JsonResponse({
        "name": "Click SuperApp",
        "short_name": "Click",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#0073ff",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

def sw_view(request):
    return HttpResponse(
        "self.addEventListener('install', e => self.skipWaiting()); self.addEventListener('fetch', e => {});",
        content_type="application/javascript"
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('wallet.urls')),
    path('manifest.json', manifest_view),
    path('sw.js', sw_view),
]