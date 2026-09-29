from django.contrib import admin

from .models import NotificationLog, Template, Trigger, UserProfile

admin.site.register(Trigger)
admin.site.register(Template)
admin.site.register(UserProfile)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "trigger_key", "channel", "user", "status", "is_test")
    list_filter = ("channel", "status", "trigger_key")
