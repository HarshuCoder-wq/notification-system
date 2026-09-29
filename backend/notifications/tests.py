from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import NotificationLog, Template, Trigger
from .providers import ProviderError, to_positional

User = get_user_model()


class RenderTests(TestCase):
    def test_variables_and_positional(self):
        call_command("seed_triggers", verbosity=0)
        t = Template.objects.create(
            trigger=Trigger.objects.get(key="login"), channel="whatsapp", body="Hi {{name}}, order {{order_id}} {{name}}"
        )
        self.assertEqual(t.variables, ["name", "order_id"])
        self.assertEqual(to_positional(t.body, t.variables), "Hi {{1}}, order {{2}} {{1}}")
        self.assertEqual(services.render("Hi {{ name }}!", {"name": "Harsh"}), "Hi Harsh!")


@override_settings(CRON_SECRET="s3cret")
class FlowTests(TestCase):
    def setUp(self):
        call_command("seed_triggers", verbosity=0)
        self.admin = User.objects.create_user("admin", "admin@x.com", "pass12345", is_staff=True, first_name="Admin")
        self.admin.profile.phone = "91 99999 99999"
        self.admin.profile.save()
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def _make_templates(self, key="login"):
        trig = Trigger.objects.get(key=key)
        with patch("notifications.providers.whatsapp_create_template", return_value={"id": "1", "status": "PENDING"}):
            r = self.api.post("/api/admin/templates/", {"trigger": trig.id, "channel": "whatsapp", "body": "Welcome back {{name}}!"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["wa_template_name"], f"nh_{key}")
        self.assertEqual(r.data["wa_status"], "PENDING")
        r = self.api.post("/api/admin/templates/", {"trigger": trig.id, "channel": "email", "subject": "Hi {{name}}", "body": "You logged in"})
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.post("/api/admin/templates/", {"trigger": trig.id, "channel": "webpush", "title": "Welcome", "body": "Hello {{name}}"})
        self.assertEqual(r.status_code, 201, r.data)
        return trig

    def test_validation(self):
        trig = Trigger.objects.get(key="login")
        r = self.api.post("/api/admin/templates/", {"trigger": trig.id, "channel": "email", "body": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("subject", r.data)

    @patch("notifications.providers.push_send", return_value={"id": "p1"})
    @patch("notifications.providers.email_send", return_value={"messageId": "e1"})
    @patch("notifications.providers.whatsapp_send", side_effect=ProviderError("token expired"))
    def test_fire_all_channels_isolated_and_toggle(self, wa, email, push):
        self._make_templates()
        logs = services.fire_trigger("login", self.admin)
        self.assertEqual(sorted(l.status for l in logs), ["failed", "sent", "sent"])  # WA failure doesn't stop others
        self.assertEqual(wa.call_args[0][1], "919999999999")  # phone normalised
        self.assertEqual(email.call_args[0][2], "Hi Admin")  # subject rendered

        tpl = Template.objects.get(channel="email")
        r = self.api.post(f"/api/admin/templates/{tpl.id}/toggle/")
        self.assertFalse(r.data["is_enabled"])
        self.assertEqual(len(services.fire_trigger("login", self.admin)), 2)

    @patch("notifications.providers.email_send", return_value={"messageId": "e1"})
    def test_test_send_and_matrix(self, email):
        self._make_templates()
        tpl = Template.objects.get(channel="email")
        r = self.api.post(f"/api/admin/templates/{tpl.id}/test/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["is_test"])
        r = self.api.get("/api/admin/matrix/")
        login_row = [row for row in r.data["rows"] if row["key"] == "login"][0]
        self.assertIsNotNone(login_row["cells"]["email"])
        self.assertIsNone(Trigger.objects.get(key="logout").templates.first())

    def test_non_admin_forbidden(self):
        user = User.objects.create_user("bob", "bob@x.com", "pass12345")
        c = APIClient()
        c.force_authenticate(user)
        self.assertEqual(c.get("/api/admin/matrix/").status_code, 403)

    @patch("notifications.services.fire_trigger_async")
    def test_register_login_logout_fire(self, fire):
        c = APIClient()
        r = c.post("/api/auth/register/", {"username": "u1", "first_name": "U", "email": "u1@x.com", "phone": "919", "password": "pass12345"})
        self.assertEqual(r.status_code, 201, r.data)
        r = c.post("/api/auth/login/", {"username": "u1@x.com", "password": "pass12345"})
        self.assertEqual(r.status_code, 200)
        fire.assert_called_with("login", r.data["user"]["id"])
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        c.post("/api/auth/logout/")
        fire.assert_called_with("logout", r.data["user"]["id"])

    @patch("notifications.providers.push_send", return_value={"id": "p1"})
    @patch("notifications.providers.email_send", return_value={"messageId": "e1"})
    @patch("notifications.providers.whatsapp_send", return_value={"messages": [{"id": "w"}]})
    def test_inactivity_job_sends_once(self, *_):
        self._make_templates("inactive_1d")
        self.admin.profile.last_seen_at = timezone.now() - timedelta(days=2)
        self.admin.profile.save()
        c = APIClient()
        self.assertEqual(c.post("/api/jobs/check-inactive/").status_code, 403)
        r = c.post("/api/jobs/check-inactive/", HTTP_X_CRON_SECRET="s3cret")
        self.assertEqual(r.data["sent"]["inactive_1d"], 1)
        r = c.post("/api/jobs/check-inactive/", HTTP_X_CRON_SECRET="s3cret")
        self.assertEqual(r.data["sent"]["inactive_1d"], 0)  # not sent twice
        self.assertEqual(NotificationLog.objects.filter(trigger_key="inactive_1d").count(), 3)
