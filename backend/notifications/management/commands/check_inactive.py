from django.core.management.base import BaseCommand

from notifications.services import check_inactive_users


class Command(BaseCommand):
    help = "Send 'not logged in for 1 day / 1 week' notifications"

    def handle(self, *args, **options):
        self.stdout.write(str(check_inactive_users()))
