from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST


def is_hr(user):
    return user.is_authenticated and user.is_hr


hr_required = user_passes_test(is_hr, login_url='accounts:login')


def _month_bounds(today):
    start = today.replace(day=1)
    next_month = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
    return start, next_month - timedelta(days=1)


@login_required
def home(request):
    from attendance.models import Attendance, CorrectionRequest
    from employees.models import Employee
    from leave.models import LeaveRequest

    today = timezone.localdate()
    employee = getattr(request.user, 'employee', None)

    context = {
        'today': today,
        'employee': employee,
        'today_record': None,
    }
    if employee:
        context['today_record'] = Attendance.objects.filter(employee=employee, date=today).first()

    if request.user.is_hr:
        context['metrics_company'] = {
            'employees': Employee.objects.filter(is_active=True).count(),
            'present_today': Attendance.objects.filter(date=today).count(),
            'pending_corrections': CorrectionRequest.objects.filter(
                state=CorrectionRequest.STATE_PENDING
            ).count(),
            'pending_leave': LeaveRequest.objects.filter(
                state=LeaveRequest.STATE_PENDING
            ).count(),
        }
    elif employee:
        month_start, month_end = _month_bounds(today)
        records = Attendance.objects.filter(
            employee=employee,
            date__gte=month_start,
            date__lte=month_end,
        )
        completed = [r for r in records if r.effective_check_in and r.effective_check_out]
        total_seconds = sum(
            (r.effective_check_out - r.effective_check_in).total_seconds() for r in completed
        )
        context['metrics_personal'] = {
            'completed_days': len(completed),
            'total_hours': round(total_seconds / 3600, 1),
            'pending_corrections': CorrectionRequest.objects.filter(
                employee=employee,
                state=CorrectionRequest.STATE_PENDING,
            ).count(),
            'pending_leave': LeaveRequest.objects.filter(
                employee=employee,
                state=LeaveRequest.STATE_PENDING,
            ).count(),
        }

    return render(request, 'home.html', context)


@login_required
@require_POST
def notifications_seen(request):
    request.user.notifications_seen_at = timezone.now()
    request.user.save(update_fields=['notifications_seen_at'])
    return JsonResponse({'status': 'ok'})
