import re

from django.conf import settings
from django.db import models

# Matches {{name}}, {{ order_id }} ...
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class Trigger(models.Model):
    """An event on the website that can cause notifications (login, logout, inactive_1d ...)."""

    key = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Channel(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "Email"
    WEBPUSH = "webpush", "Web Push"


class Template(models.Model):
    """One cell of the admin table: a message for one trigger on one channel."""

    WA_MODES = [("template", "Approved template"), ("text", "Free-form text (24h window)")]
    WA_CATEGORIES = [("UTILITY", "Utility"), ("MARKETING", "Marketing")]

    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE, related_name="templates")
    channel = models.CharField(max_length=20, choices=Channel.choices)

    subject = models.CharField(max_length=200, blank=True)  # email
    title = models.CharField(max_length=200, blank=True)  # web push
    body = models.TextField()
    # Variable mapping: ordered list of placeholders used in the template.
    # For WhatsApp, variables[0] -> {{1}}, variables[1] -> {{2}} ...
    variables = models.JSONField(default=list, blank=True)
    is_enabled = models.BooleanField(default=True)

    # WhatsApp-only fields
    wa_mode = models.CharField(max_length=10, choices=WA_MODES, default="template")
    wa_template_name = models.CharField(max_length=100, blank=True)
    wa_template_id = models.CharField(max_length=64, blank=True)
    wa_language = models.CharField(max_length=10, default="en_US")
    wa_category = models.CharField(max_length=20, choices=WA_CATEGORIES, default="UTILITY")
    wa_status = models.CharField(max_length=20, default="DRAFT")  # DRAFT/PENDING/APPROVED/REJECTED/ERROR
    wa_last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("trigger", "channel")
        ordering = ["trigger_id", "channel"]

    def __str__(self):
        return f"{self.trigger.key} / {self.channel}"

    def extract_variables(self):
        seen = []
        for text in (self.subject, self.title, self.body):
            for name in VAR_RE.findall(text or ""):
                if name not in seen:
                    seen.append(name)
        return seen

    def save(self, *args, **kwargs):
        self.variables = self.extract_variables()
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True, help_text="With country code, e.g. 919876543210")
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Profile({self.user})"


class NotificationLog(models.Model):
    STATUS = [("sent", "Sent"), ("failed", "Failed")]

    trigger = models.ForeignKey(Trigger, on_delete=models.SET_NULL, null=True, blank=True)
    trigger_key = models.CharField(max_length=50)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    recipient = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS)
    is_test = models.BooleanField(default=False)
    response = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
