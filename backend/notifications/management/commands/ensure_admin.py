import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from notifications.models import UserProfile


class Command(BaseCommand):
    help = "Create/update the admin user from ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_EMAIL / ADMIN_PHONE env vars"

    def handle(self, *args, **options):
        username = os.getenv("ADMIN_USERNAME")
        password = os.getenv("ADMIN_PASSWORD")
        if not username or not password:
            self.stdout.write("ADMIN_USERNAME / ADMIN_PASSWORD not set - skipping")
            return
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.email = os.getenv("ADMIN_EMAIL", user.email)
        user.first_name = user.first_name or "Admin"
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        phone = os.getenv("ADMIN_PHONE")
        if phone:
            UserProfile.objects.update_or_create(user=user, defaults={"phone": phone})
        self.stdout.write(f"Admin {'created' if created else 'updated'}: {username}")
