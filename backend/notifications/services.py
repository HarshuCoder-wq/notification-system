"""
Core notification logic.

    fire_trigger("login", user)  ->  for every ENABLED template of that trigger
                                     render variables -> send via provider -> log

One channel failing never stops the other channels.
"""
import logging
import re
import threading
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.utils import timezone

from . import providers
from .models import VAR_RE, Channel, NotificationLog, Template, Trigger, UserProfile
from .providers import ProviderError

log = logging.getLogger("notifications")

INACTIVITY_TRIGGERS = [("inactive_1d", timedelta(days=1)), ("inactive_1w", timedelta(days=7))]


def normalize_phone(phone):
    return re.sub(r"\D", "", phone or "")


def build_context(user, extra=None):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    now = timezone.localtime()
    ctx = {
        "name": user.first_name or user.username,
        "first_name": user.first_name or user.username,
        "username": user.username,
        "email": user.email,
        "phone": profile.phone,
        "app_name": settings.APP_NAME,
        "date": now.strftime("%d %b %Y"),
        "time": now.strftime("%I:%M %p"),
        "link": settings.FRONTEND_URL,
    }
    ctx.update(extra or {})
    return ctx


def render(text, ctx):
    return VAR_RE.sub(lambda m: str(ctx.get(m.group(1), "")), text or "")


def send_template(template, user, extra=None, is_test=False):
    """Send one template to one user. Always returns a saved NotificationLog."""
    ctx = build_context(user, {"trigger": template.trigger.name, **(extra or {})})
    entry = NotificationLog(
        trigger=template.trigger,
        trigger_key=template.trigger.key,
        channel=template.channel,
        user=user,
        is_test=is_test,
    )
    try:
        body = render(template.body, ctx)
        if template.channel == Channel.WHATSAPP:
            phone = normalize_phone(user.profile.phone)
            if not phone:
                raise ProviderError("User has no phone number saved")
            entry.recipient = phone
            resp = providers.whatsapp_send(template, phone, ctx, body)
        elif template.channel == Channel.EMAIL:
            if not user.email:
                raise ProviderError("User has no email saved")
            entry.recipient = user.email
            resp = providers.email_send(user.email, ctx["name"], render(template.subject, ctx), body)
        else:
            entry.recipient = f"external_id:{user.id}"
            resp = providers.push_send(user.id, render(template.title, ctx), body, settings.FRONTEND_URL)
        entry.status = "sent"
        entry.response = resp
    except ProviderError as exc:
        entry.status = "failed"
        entry.error = str(exc)
        entry.response = exc.response
    except Exception as exc:  # never let one channel crash the others
        log.exception("Unexpected error sending %s", template)
        entry.status = "failed"
        entry.error = f"Unexpected error: {exc}"
    entry.save()
    log.info("[%s] %s -> %s : %s %s", entry.trigger_key, entry.channel, entry.recipient, entry.status, entry.error)
    return entry


def fire_trigger(key, user, extra=None):
    trigger = Trigger.objects.filter(key=key, is_active=True).first()
    if not trigger:
        return []
    templates = Template.objects.filter(trigger=trigger, is_enabled=True).select_related("trigger")
    return [send_template(t, user, extra) for t in templates]


def fire_trigger_async(key, user_id, extra=None):
    """Run in a background thread so login/logout API responds instantly."""

    def run():
        close_old_connections()
        try:
            user = get_user_model().objects.get(pk=user_id)
            fire_trigger(key, user, extra)
        except Exception:
            log.exception("fire_trigger_async failed for %s", key)
        finally:
            close_old_connections()

    threading.Thread(target=run, daemon=True).start()


def check_inactive_users():
    """
    Called hourly (GitHub Actions cron -> /api/jobs/check-inactive/).
    Sends 'inactive_1d' / 'inactive_1w' once per inactivity period:
    we skip a user if we already logged that trigger for them after their last visit.
    """
    now = timezone.now()
    sent = {}
    for key, delta in INACTIVITY_TRIGGERS:
        count = 0
        trigger = Trigger.objects.filter(key=key, is_active=True).first()
        if not trigger or not trigger.templates.filter(is_enabled=True).exists():
            sent[key] = 0
            continue
        profiles = UserProfile.objects.select_related("user").filter(
            last_seen_at__isnull=False, last_seen_at__lte=now - delta, user__is_active=True
        )
        for profile in profiles:
            already = NotificationLog.objects.filter(
                user=profile.user, trigger_key=key, is_test=False, created_at__gte=profile.last_seen_at
            ).exists()
            if already:
                continue
            fire_trigger(key, profile.user)
            count += 1
        sent[key] = count
    return sent


def touch_last_seen(user):
    UserProfile.objects.update_or_create(user=user, defaults={"last_seen_at": timezone.now()})
