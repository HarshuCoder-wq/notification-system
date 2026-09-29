import random

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import providers, services
from .models import Channel, NotificationLog, Template, Trigger
from .providers import ProviderError
from .serializers import (
    LogSerializer,
    MatrixRowSerializer,
    RegisterSerializer,
    TemplateSerializer,
    TriggerSerializer,
    UserSerializer,
)

User = get_user_model()


def auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data}


# ---------------------------------------------------------------------------
# Website (user side) - these endpoints FIRE triggers
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        services.touch_last_seen(user)
        return Response(auth_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        if "@" in identifier:
            match = User.objects.filter(email__iexact=identifier).first()
            identifier = match.username if match else identifier
        user = authenticate(request, username=identifier, password=password)
        if not user:
            return Response({"detail": "Invalid username or password"}, status=status.HTTP_401_UNAUTHORIZED)
        services.touch_last_seen(user)
        services.fire_trigger_async("login", user.id)  # TRIGGER: login
        return Response(auth_payload(user))


class LogoutView(APIView):
    def post(self, request):
        services.fire_trigger_async("logout", request.user.id)  # TRIGGER: logout
        return Response({"detail": "Logged out"})


class MeView(APIView):
    def get(self, request):
        services.touch_last_seen(request.user)  # visiting the site counts as activity
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        ser = UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class OrderView(APIView):
    """Demo purchase so 'Order placed' can be fired from the website."""

    def post(self, request):
        order = {"order_id": f"ORD{random.randint(1000, 9999)}", "amount": str(request.data.get("amount") or 499)}
        services.fire_trigger_async("order_placed", request.user.id, order)  # TRIGGER: order placed
        return Response({"detail": "Order placed", **order})


class PasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        user = User.objects.filter(email__iexact=email).first() if email else None
        if user:
            services.fire_trigger_async(
                "password_reset", user.id, {"link": f"{settings.FRONTEND_URL}/login"}
            )  # TRIGGER: password reset
        return Response({"detail": "If this email is registered, a reset message has been sent."})


# ---------------------------------------------------------------------------
# Admin panel APIs
# ---------------------------------------------------------------------------
class MatrixView(APIView):
    """Everything the admin table needs in one call: rows = triggers, columns = channels."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        triggers = Trigger.objects.prefetch_related("templates").all()
        return Response({"channels": [c.value for c in Channel], "rows": MatrixRowSerializer(triggers, many=True).data})


class TriggerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Trigger.objects.all()
    serializer_class = TriggerSerializer

    @action(detail=True, methods=["post"])
    def fire(self, request, pk=None):
        """Fire this trigger for the logged-in admin right now (demo for inactivity triggers)."""
        trigger = self.get_object()
        logs = services.fire_trigger(trigger.key, request.user, {"order_id": "ORD0001", "amount": "499"})
        if not logs:
            return Response({"detail": "No enabled templates for this trigger", "logs": []})
        return Response({"detail": f"Fired {trigger.name}", "logs": LogSerializer(logs, many=True).data})


class TemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Template.objects.select_related("trigger").all()
    serializer_class = TemplateSerializer

    # --- WhatsApp: templates are created on Meta from here, admin never opens Meta ---
    def _submit_whatsapp(self, template, previous=None):
        if template.channel != Channel.WHATSAPP or template.wa_mode != "template":
            return
        try:
            name_changed = previous is None or previous["wa_template_name"] != template.wa_template_name
            if name_changed or not template.wa_template_id:
                resp = providers.whatsapp_create_template(template)
                template.wa_template_id = str(resp.get("id", ""))
                template.wa_status = resp.get("status", "PENDING")
            elif previous["body"] != template.body:
                providers.whatsapp_edit_template(template)
                template.wa_status = "PENDING"
            template.wa_last_error = ""
        except ProviderError as exc:
            # Template name already exists on Meta -> just link to it
            existing = self._safe_fetch(template)
            if existing:
                template.wa_template_id = existing.get("id", "")
                template.wa_status = existing.get("status", "PENDING")
                template.wa_last_error = f"Linked to existing Meta template. ({exc})"
            else:
                template.wa_status = "ERROR"
                template.wa_last_error = str(exc)
        template.save(update_fields=["wa_template_id", "wa_status", "wa_last_error", "variables"])

    def _safe_fetch(self, template):
        try:
            return providers.whatsapp_fetch_template(template)
        except ProviderError:
            return None

    def perform_create(self, serializer):
        template = serializer.save()
        self._submit_whatsapp(template)

    def perform_update(self, serializer):
        before = {"wa_template_name": serializer.instance.wa_template_name, "body": serializer.instance.body}
        template = serializer.save()
        self._submit_whatsapp(template, before)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        template = self.get_object()
        template.is_enabled = not template.is_enabled
        template.save(update_fields=["is_enabled", "variables", "updated_at"])
        return Response(TemplateSerializer(template).data)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Test send to the admin (or ?user_id=) even if the toggle is off."""
        template = self.get_object()
        target = request.user
        if request.data.get("user_id"):
            target = User.objects.filter(pk=request.data["user_id"]).first() or request.user
        entry = services.send_template(template, target, {"order_id": "TEST123", "amount": "499"}, is_test=True)
        code = status.HTTP_200_OK if entry.status == "sent" else status.HTTP_502_BAD_GATEWAY
        return Response(LogSerializer(entry).data, status=code)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Pull the latest WhatsApp approval status from Meta."""
        template = self.get_object()
        if template.channel != Channel.WHATSAPP or template.wa_mode != "template":
            return Response({"detail": "Only WhatsApp approved-template mode needs sync"}, status=400)
        try:
            remote = providers.whatsapp_fetch_template(template)
        except ProviderError as exc:
            template.wa_last_error = str(exc)
            template.save(update_fields=["wa_last_error", "variables"])
            return Response(TemplateSerializer(template).data, status=status.HTTP_502_BAD_GATEWAY)
        if remote:
            template.wa_template_id = remote.get("id", template.wa_template_id)
            template.wa_status = remote.get("status", template.wa_status)
            template.wa_last_error = ""
        else:
            # Not found on Meta (maybe token/WABA changed) -> try creating it again
            self._submit_whatsapp(template, {"wa_template_name": "", "body": ""})
            template.refresh_from_db()
        template.save(update_fields=["wa_template_id", "wa_status", "wa_last_error", "variables"])
        return Response(TemplateSerializer(template).data)


class LogListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        logs = NotificationLog.objects.select_related("user")[:50]
        return Response(LogSerializer(logs, many=True).data)


# ---------------------------------------------------------------------------
# Scheduled job (called hourly by GitHub Actions)
# ---------------------------------------------------------------------------
class CheckInactiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = request.headers.get("X-Cron-Secret") or request.query_params.get("secret")
        if not settings.CRON_SECRET or secret != settings.CRON_SECRET:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        return Response({"sent": services.check_inactive_users()})
