from django.contrib import admin
from .models import Bot, BotAssignment


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ['name', 'api_url', 'friend_count', 'is_active', 'last_used']
    list_editable = ['is_active']


@admin.register(BotAssignment)
class BotAssignmentAdmin(admin.ModelAdmin):
    list_display = ['order', 'bot', 'epic_account_id', 'assigned_at']
