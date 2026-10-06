from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Verito Tech"
admin.site.site_title = "Verito Tech"
admin.site.index_title = "Shop books"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("books.api_urls")),
    path("", include("books.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
