from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from services.views import ProfileImageUploadView, RegisterView


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),
    path(
        "api/v1/services/",
        include("services.urls"),
    ),
    path(
        "api/v1/",
        include("services.booking_urls"),
    ),
    path(
        "api/v1/profile/image/",
        ProfileImageUploadView.as_view(),
        name="profile-image-upload",
    ),
    path(
        "api/v1/register/",
        RegisterView.as_view(),
        name="register",
    ),
    path(
        "api/v1/token/",
        TokenObtainPairView.as_view(),
        name="token-obtain-pair",
    ),
    path(
        "api/v1/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
]