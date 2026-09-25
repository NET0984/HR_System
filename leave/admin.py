from django.contrib import admin

from .models import LeaveRequest


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'state', 'requester', 'reviewer', 'decided_at')
    list_filter = ('state', 'leave_type', 'start_date')
    search_fields = ('employee__employee_code', 'employee__full_name', 'reason')
    date_hierarchy = 'start_date'
    readonly_fields = ('created_at', 'updated_at')
