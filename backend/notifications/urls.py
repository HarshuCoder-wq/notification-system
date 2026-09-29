from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("admin/triggers", views.TriggerViewSet, basename="trigger")
router.register("admin/templates", views.TemplateViewSet, basename="template")

urlpatterns = [
    path("health/", views.health),
    # Website auth (fires login / logout / password_reset)
    path("auth/register/", views.RegisterView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("auth/password-reset/", views.PasswordResetView.as_view()),
    path("orders/", views.OrderView.as_view()),
    # Admin panel
    path("admin/matrix/", views.MatrixView.as_view()),
    path("admin/logs/", views.LogListView.as_view()),
    path("", include(router.urls)),
    # Cron
    path("jobs/check-inactive/", views.CheckInactiveView.as_view()),
]
