from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'entity_type', 'entity_id')
    list_filter = ('action', 'entity_type')
    search_fields = ('actor__username', 'entity_type', 'action')
    date_hierarchy = 'created_at'
    readonly_fields = ('actor', 'action', 'entity_type', 'entity_id', 'before', 'after', 'reason', 'created_at')
