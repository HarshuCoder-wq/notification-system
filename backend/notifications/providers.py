"""
Provider adapters. Each channel talks to one external service:

    WhatsApp -> Meta WhatsApp Cloud API (sandbox / test number)
    Email    -> Brevo transactional email API (free tier)
    Web Push -> OneSignal REST API (web push only)

Every function either returns the provider's JSON response or raises ProviderError,
so the service layer can log success/failure the same way for all channels.
"""
import html
import logging

import requests
from django.conf import settings

from .models import VAR_RE

log = logging.getLogger("notifications")
TIMEOUT = 15

SAMPLE_VALUES = {
    "name": "Harsh",
    "first_name": "Harsh",
    "username": "harsh",
    "email": "user@example.com",
    "phone": "919999999999",
    "app_name": "NotifyHub",
    "order_id": "ORD1234",
    "amount": "499",
    "date": "29 Sep 2026",
    "time": "10:30 AM",
    "trigger": "Login",
    "link": "https://example.com",
}


class ProviderError(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response or {}


def _require(value, name):
    if not value:
        raise ProviderError(f"{name} is not configured on the server")
    return value


def _request(method, url, **kwargs):
    try:
        r = requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise ProviderError(f"Network error: {exc}")
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:500]}
    if r.status_code >= 400:
        raise ProviderError(_error_message(data, r.status_code), data)
    return data


def _error_message(data, status):
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):  # Meta style
            return err.get("error_user_msg") or err.get("message") or str(err)
        if data.get("message"):  # Brevo style
            return str(data["message"])
        if data.get("errors"):  # OneSignal style
            return str(data["errors"])
    return f"HTTP {status}: {data}"


# ---------------------------------------------------------------------------
# WhatsApp Cloud API
# ---------------------------------------------------------------------------
def _graph(path):
    return f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{path}"


def _wa_headers():
    token = _require(settings.WHATSAPP_ACCESS_TOKEN, "WHATSAPP_ACCESS_TOKEN")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def to_positional(text, variables):
    """'Hi {{name}}' + ['name'] -> 'Hi {{1}}' (WhatsApp only accepts numbered params)."""
    return VAR_RE.sub(lambda m: "{{%d}}" % (variables.index(m.group(1)) + 1), text)


def _wa_components(template):
    component = {"type": "BODY", "text": to_positional(template.body, template.variables)}
    if template.variables:
        component["example"] = {"body_text": [[SAMPLE_VALUES.get(v, "sample") for v in template.variables]]}
    return [component]


def whatsapp_create_template(template):
    waba = _require(settings.WHATSAPP_BUSINESS_ACCOUNT_ID, "WHATSAPP_BUSINESS_ACCOUNT_ID")
    payload = {
        "name": template.wa_template_name,
        "language": template.wa_language,
        "category": template.wa_category,
        "components": _wa_components(template),
    }
    return _request("POST", _graph(f"{waba}/message_templates"), headers=_wa_headers(), json=payload)


def whatsapp_edit_template(template):
    payload = {"components": _wa_components(template)}
    return _request("POST", _graph(template.wa_template_id), headers=_wa_headers(), json=payload)


def whatsapp_fetch_template(template):
    """Returns {'id','status','name','language'} for this template from Meta, or None."""
    waba = _require(settings.WHATSAPP_BUSINESS_ACCOUNT_ID, "WHATSAPP_BUSINESS_ACCOUNT_ID")
    data = _request(
        "GET",
        _graph(f"{waba}/message_templates"),
        headers=_wa_headers(),
        params={"name": template.wa_template_name, "fields": "id,name,status,language"},
    )
    for item in data.get("data", []):
        if item.get("name") == template.wa_template_name and item.get("language") == template.wa_language:
            return item
    return None


def whatsapp_send(template, phone, context, rendered_body):
    phone_id = _require(settings.WHATSAPP_PHONE_NUMBER_ID, "PHONE_NUMBER_ID")
    if template.wa_mode == "text":
        # Free-form text only works inside the 24h customer-service window
        payload = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": rendered_body}}
    else:
        tpl = {"name": template.wa_template_name, "language": {"code": template.wa_language}}
        if template.variables:
            tpl["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(context.get(v, "") or "-")} for v in template.variables],
                }
            ]
        payload = {"messaging_product": "whatsapp", "to": phone, "type": "template", "template": tpl}
    return _request("POST", _graph(f"{phone_id}/messages"), headers=_wa_headers(), json=payload)


# ---------------------------------------------------------------------------
# Email (Brevo)
# ---------------------------------------------------------------------------
def email_send(to_email, to_name, subject, body):
    api_key = _require(settings.BREVO_API_KEY, "BREVO_API_KEY")
    sender = _require(settings.BREVO_FROM_EMAIL, "BREVO_FROM_EMAIL")
    html_body = (
        '<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.6;color:#222">'
        + html.escape(body).replace("\n", "<br>")
        + f'<hr style="border:none;border-top:1px solid #eee;margin-top:24px">'
        f'<small style="color:#888">Sent by {html.escape(settings.APP_NAME)}</small></div>'
    )
    payload = {
        "sender": {"name": settings.BREVO_FROM_NAME, "email": sender},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": body,
    }
    headers = {"api-key": api_key, "accept": "application/json", "content-type": "application/json"}
    return _request("POST", "https://api.brevo.com/v3/smtp/email", headers=headers, json=payload)


# ---------------------------------------------------------------------------
# Web Push (OneSignal)
# ---------------------------------------------------------------------------
def push_send(external_id, title, body, url=None):
    app_id = _require(settings.ONESIGNAL_APP_ID, "ONESIGNAL_APP_ID")
    key = _require(settings.ONESIGNAL_REST_API_KEY.strip().strip('"'), "ONESIGNAL_REST_API_KEY")
    if key.startswith("PASTE_") or key.startswith("your_"):
        raise ProviderError("ONESIGNAL_REST_API_KEY is still a placeholder in .env - paste the real os_v2_app_... key")
    # New keys (os_v2_...) use "Key", old legacy keys use "Basic"
    scheme = "Key" if key.startswith("os_v2") else "Basic"
    payload = {
        "app_id": app_id,
        "target_channel": "push",
        "include_aliases": {"external_id": [str(external_id)]},
        "headings": {"en": title},
        "contents": {"en": body},
        # Web push only: iOS / Android turned off
        "isAnyWeb": True,
        "isIos": False,
        "isAndroid": False,
    }
    if url:
        payload["web_url"] = url
    headers = {"Authorization": f"{scheme} {key}", "Content-Type": "application/json"}
    data = _request("POST", "https://api.onesignal.com/notifications?c=push", headers=headers, json=payload)
    if not data.get("id") or data.get("errors"):
        raise ProviderError(
            "Push not delivered: this user has not enabled browser notifications yet "
            "(click 'Enable notifications' on the website).",
            data,
        )
    return data