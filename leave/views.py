from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import hr_required
from audit.models import AuditLog
from audit.services import record as audit_record
from employees.models import Employee

from .forms import LeaveCancelForm, LeaveDecisionForm, LeaveRequestForm
from .models import LeaveRequest


def _current_employee(user):
    return getattr(user, 'employee', None)


def _leave_snapshot(leave):
    return {
        'leave_type': leave.leave_type,
        'start_date': str(leave.start_date),
        'end_date': str(leave.end_date),
        'state': leave.state,
    }


def _decision_reason(request):
    form = LeaveDecisionForm(request.POST)
    if form.is_valid():
        return form.cleaned_data['decision_reason']
    return ''


def _overlapping_requests(employee, start, end, exclude_pk=None):
    queryset = LeaveRequest.objects.filter(
        employee=employee,
        state__in=[LeaveRequest.STATE_PENDING, LeaveRequest.STATE_APPROVED],
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()


@login_required
def leave_list(request):
    employee = _current_employee(request.user)
    leave_requests = LeaveRequest.objects.none()
    if employee:
        leave_requests = LeaveRequest.objects.filter(employee=employee).select_related('reviewer')

    context = {
        'employee': employee,
        'leave_requests': leave_requests,
    }
    return render(request, 'leave/list.html', context)


@login_required
def leave_create(request):
    employee = _current_employee(request.user)
    if not employee:
        messages.error(request, 'Tài khoản của bạn chưa gắn hồ sơ nhân viên nên chưa thể gửi đơn nghỉ phép.')
        return redirect('leave:list')

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, employee=employee)
        if form.is_valid():
            start = form.cleaned_data['start_date']
            end = form.cleaned_data['end_date']
            with transaction.atomic():
                Employee.objects.select_for_update().get(pk=employee.pk)
                if _overlapping_requests(employee, start, end):
                    messages.error(request, 'Khoảng nghỉ trùng với một đơn đang chờ duyệt hoặc đã duyệt.')
                    return redirect('leave:create')

                leave = form.save(commit=False)
                leave.employee = employee
                leave.requester = request.user
                leave.save()
                audit_record(
                    request.user,
                    'leave.create',
                    'LeaveRequest',
                    leave.pk,
                    after=_leave_snapshot(leave),
                    reason=leave.reason,
                )
            messages.success(request, 'Đã gửi đơn nghỉ phép. Vui lòng chờ HR duyệt.')
            return redirect('leave:list')
    else:
        form = LeaveRequestForm(employee=employee)

    return render(request, 'leave/form.html', {'form': form, 'employee': employee})


@login_required
@require_POST
def leave_cancel(request, pk):
    employee = _current_employee(request.user)
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if not employee or leave.employee_id != employee.pk:
        messages.error(request, 'Bạn không thể hủy đơn này.')
        return redirect('leave:list')
    if not leave.is_pending:
        messages.error(request, 'Chỉ có thể hủy đơn đang chờ duyệt.')
        return redirect('leave:detail', pk=pk)

    form = LeaveCancelForm(request.POST)
    reason = form.cleaned_data['cancellation_reason'] if form.is_valid() else ''

    leave.state = LeaveRequest.STATE_CANCELLED
    leave.cancelled_by = request.user
    leave.cancelled_at = timezone.now()
    leave.cancellation_reason = reason
    leave.save(update_fields=['state', 'cancelled_by', 'cancelled_at', 'cancellation_reason', 'updated_at'])
    audit_record(
        request.user,
        'leave.cancel',
        'LeaveRequest',
        leave.pk,
        before={'state': LeaveRequest.STATE_PENDING},
        after={'state': LeaveRequest.STATE_CANCELLED},
        reason=reason,
    )
    messages.success(request, 'Đã hủy đơn nghỉ phép.')
    return redirect('leave:list')


@hr_required
def leave_queue(request):
    state = request.GET.get('state', LeaveRequest.STATE_PENDING)
    queryset = LeaveRequest.objects.select_related('employee', 'requester', 'reviewer')
    if state == 'all':
        pass
    elif state in dict(LeaveRequest.STATE_CHOICES):
        queryset = queryset.filter(state=state)
    else:
        state = LeaveRequest.STATE_PENDING
        queryset = queryset.filter(state=LeaveRequest.STATE_PENDING)

    page_obj = Paginator(queryset, 15).get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'selected_state': state,
        'state_choices': LeaveRequest.STATE_CHOICES,
        'pending_count': LeaveRequest.objects.filter(state=LeaveRequest.STATE_PENDING).count(),
    }
    return render(request, 'leave/queue.html', context)


@login_required
def leave_detail(request, pk):
    leave = get_object_or_404(
        LeaveRequest.objects.select_related('employee', 'requester', 'reviewer', 'cancelled_by'),
        pk=pk,
    )
    employee = _current_employee(request.user)
    is_owner = employee is not None and leave.employee_id == employee.pk
    if not (request.user.is_hr or is_owner):
        messages.error(request, 'Bạn không có quyền xem đơn này.')
        return redirect('leave:list')

    audit_logs = AuditLog.objects.filter(
        entity_type='LeaveRequest',
        entity_id=leave.pk,
    ).select_related('actor')
    context = {
        'leave': leave,
        'is_owner': is_owner,
        'audit_logs': audit_logs,
    }
    return render(request, 'leave/detail.html', context)


@hr_required
@require_POST
def leave_approve(request, pk):
    with transaction.atomic():
        leave = get_object_or_404(LeaveRequest, pk=pk)
        Employee.objects.select_for_update().get(pk=leave.employee_id)
        leave = LeaveRequest.objects.select_for_update().get(pk=pk)

        if not leave.is_pending:
            messages.error(request, 'Đơn này đã được xử lý.')
            return redirect('leave:detail', pk=pk)
        if leave.requester_id == request.user.id:
            messages.error(request, 'Bạn không thể tự duyệt đơn của chính mình.')
            return redirect('leave:detail', pk=pk)

        leave.state = LeaveRequest.STATE_APPROVED
        leave.reviewer = request.user
        leave.decided_at = timezone.now()
        leave.decision_reason = _decision_reason(request)
        leave.save(update_fields=['state', 'reviewer', 'decided_at', 'decision_reason', 'updated_at'])
        audit_record(
            request.user,
            'leave.approve',
            'LeaveRequest',
            leave.pk,
            before={'state': LeaveRequest.STATE_PENDING},
            after={'state': LeaveRequest.STATE_APPROVED},
            reason=leave.decision_reason,
        )

    messages.success(request, 'Đã duyệt đơn nghỉ phép.')
    return redirect('leave:detail', pk=pk)


@hr_required
@require_POST
def leave_reject(request, pk):
    with transaction.atomic():
        leave = get_object_or_404(LeaveRequest, pk=pk)
        Employee.objects.select_for_update().get(pk=leave.employee_id)
        leave = LeaveRequest.objects.select_for_update().get(pk=pk)

        if not leave.is_pending:
            messages.error(request, 'Đơn này đã được xử lý.')
            return redirect('leave:detail', pk=pk)
        if leave.requester_id == request.user.id:
            messages.error(request, 'Bạn không thể tự xử lý đơn của chính mình.')
            return redirect('leave:detail', pk=pk)

        leave.state = LeaveRequest.STATE_REJECTED
        leave.reviewer = request.user
        leave.decided_at = timezone.now()
        leave.decision_reason = _decision_reason(request)
        leave.save(update_fields=['state', 'reviewer', 'decided_at', 'decision_reason', 'updated_at'])
        audit_record(
            request.user,
            'leave.reject',
            'LeaveRequest',
            leave.pk,
            before={'state': LeaveRequest.STATE_PENDING},
            after={'state': LeaveRequest.STATE_REJECTED},
            reason=leave.decision_reason,
        )

    messages.success(request, 'Đã từ chối đơn nghỉ phép.')
    return redirect('leave:detail', pk=pk)


@hr_required
@require_POST
def leave_hr_cancel(request, pk):
    form = LeaveCancelForm(request.POST, require_reason=True)
    if not form.is_valid():
        messages.error(request, 'Vui lòng nhập lý do hủy đơn đã duyệt.')
        return redirect('leave:detail', pk=pk)
    reason = form.cleaned_data['cancellation_reason']

    with transaction.atomic():
        leave = get_object_or_404(LeaveRequest, pk=pk)
        Employee.objects.select_for_update().get(pk=leave.employee_id)
        leave = LeaveRequest.objects.select_for_update().get(pk=pk)

        if not leave.is_approved:
            messages.error(request, 'Chỉ có thể hủy đơn đã duyệt.')
            return redirect('leave:detail', pk=pk)

        leave.state = LeaveRequest.STATE_CANCELLED
        leave.cancelled_by = request.user
        leave.cancelled_at = timezone.now()
        leave.cancellation_reason = reason
        leave.save(update_fields=['state', 'cancelled_by', 'cancelled_at', 'cancellation_reason', 'updated_at'])
        audit_record(
            request.user,
            'leave.hr_cancel',
            'LeaveRequest',
            leave.pk,
            before={'state': LeaveRequest.STATE_APPROVED},
            after={'state': LeaveRequest.STATE_CANCELLED},
            reason=reason,
        )

    messages.success(request, 'Đã hủy đơn nghỉ phép đã duyệt.')
    return redirect('leave:detail', pk=pk)
