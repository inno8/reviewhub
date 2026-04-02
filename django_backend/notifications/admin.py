from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'type', 'title', 'read', 'created_at']
    list_filter = ['type', 'read', 'created_at']
    search_fields = ['title', 'message', 'user__email']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
