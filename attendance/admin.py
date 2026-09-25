from django.contrib import admin

from .models import Attendance, CorrectionRequest


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'effective_check_in', 'effective_check_out', 'missing_checkout', 'revision', 'source')
    list_filter = ('source', 'date')
    search_fields = ('employee__employee_code', 'employee__full_name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(boolean=True, description='Thiếu giờ ra')
    def missing_checkout(self, obj):
        return obj.is_incomplete


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'state', 'proposed_check_in', 'proposed_check_out', 'requester', 'reviewer', 'decided_at')
    list_filter = ('state', 'date')
    search_fields = ('employee__employee_code', 'employee__full_name', 'reason')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')
