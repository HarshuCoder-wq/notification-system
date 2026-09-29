from django.core.management.base import BaseCommand

from notifications.models import Trigger

DEFAULT_TRIGGERS = [
    ("login", "Login", "User signs in on the website"),
    ("logout", "Logout", "User signs out"),
    ("inactive_1d", "Not logged in for 1 day", "User has not visited the website for 24 hours"),
    ("inactive_1w", "Not logged in for 1 week", "User has not visited for 7 days"),
    ("password_reset", "Password reset", "User asks to reset password"),
    ("order_placed", "Order placed", "User completes a purchase"),
]


class Command(BaseCommand):
    help = "Create the default triggers (safe to run many times)"

    def handle(self, *args, **options):
        for key, name, desc in DEFAULT_TRIGGERS:
            _, created = Trigger.objects.get_or_create(key=key, defaults={"name": name, "description": desc})
            self.stdout.write(f"{'created' if created else 'exists '}  {key}")
