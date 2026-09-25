from django.contrib import admin

from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_code', 'full_name', 'department', 'joining_date', 'is_active')
    list_filter = ('is_active', 'department')
    search_fields = ('employee_code', 'full_name', 'work_email')
    readonly_fields = ('employee_code', 'created_at', 'updated_at')
