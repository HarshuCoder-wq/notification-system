import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Channel, NotificationLog, Template, Trigger, UserProfile

User = get_user_model()
WA_NAME_RE = re.compile(r"^[a-z0-9_]{1,100}$")


class UserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="profile.phone", allow_blank=True, required=False)
    last_seen_at = serializers.DateTimeField(source="profile.last_seen_at", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "email", "phone", "is_staff", "last_seen_at"]
        read_only_fields = ["id", "username", "is_staff", "last_seen_at"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if "phone" in profile_data:
            UserProfile.objects.update_or_create(user=instance, defaults={"phone": profile_data["phone"]})
        return instance


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already taken")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, data):
        user = User.objects.create_user(
            username=data["username"], email=data["email"], password=data["password"], first_name=data["first_name"]
        )
        UserProfile.objects.update_or_create(user=user, defaults={"phone": data.get("phone", "")})
        return user


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = [
            "id", "trigger", "channel", "subject", "title", "body", "variables", "is_enabled",
            "wa_mode", "wa_template_name", "wa_template_id", "wa_language", "wa_category",
            "wa_status", "wa_last_error", "updated_at",
        ]
        read_only_fields = ["variables", "wa_template_id", "wa_status", "wa_last_error", "updated_at"]
        extra_kwargs = {"is_enabled": {"default": True}}

    def validate(self, attrs):
        channel = attrs.get("channel", getattr(self.instance, "channel", None))
        trigger = attrs.get("trigger", getattr(self.instance, "trigger", None))
        get = lambda f: attrs.get(f, getattr(self.instance, f, ""))  # noqa: E731

        if not (get("body") or "").strip():
            raise serializers.ValidationError({"body": "Message body is required"})
        if channel == Channel.EMAIL and not (get("subject") or "").strip():
            raise serializers.ValidationError({"subject": "Email subject is required"})
        if channel == Channel.WEBPUSH and not (get("title") or "").strip():
            raise serializers.ValidationError({"title": "Push title is required"})
        if channel == Channel.WHATSAPP and get("wa_mode") != "text":
            name = (get("wa_template_name") or "").strip()
            if not name and trigger:
                name = f"nh_{trigger.key}".replace("-", "_")
            if not WA_NAME_RE.match(name):
                raise serializers.ValidationError(
                    {"wa_template_name": "Only lowercase letters, numbers and underscores"}
                )
            attrs["wa_template_name"] = name
        return attrs


class TriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trigger
        fields = ["id", "key", "name", "description", "is_active"]


class MatrixRowSerializer(serializers.ModelSerializer):
    """One row of the admin table: trigger + its 3 channel cells."""

    cells = serializers.SerializerMethodField()

    class Meta:
        model = Trigger
        fields = ["id", "key", "name", "description", "is_active", "cells"]

    def get_cells(self, obj):
        by_channel = {t.channel: TemplateSerializer(t).data for t in obj.templates.all()}
        return {c.value: by_channel.get(c.value) for c in Channel}


class LogSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", default=None)

    class Meta:
        model = NotificationLog
        fields = ["id", "trigger_key", "channel", "user", "recipient", "status", "is_test", "error", "created_at"]
