from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import hr_required
from audit.models import AuditLog
from audit.services import record as audit_record
from employees.models import Department, Employee

from .forms import CorrectionDecisionForm, CorrectionRequestForm, HRAttendanceEditForm
from .models import Attendance, CorrectionRequest


def _current_employee(user):
    return getattr(user, 'employee', None)


def _attendance_snapshot(attendance):
    if attendance is None:
        return None
    return {
        'effective_check_in': attendance.effective_check_in.isoformat() if attendance.effective_check_in else None,
        'effective_check_out': attendance.effective_check_out.isoformat() if attendance.effective_check_out else None,
        'revision': attendance.revision,
        'source': attendance.source,
    }


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _month_options(today):
    options = []
    year, month = today.year, today.month
    for _ in range(12):
        options.append((f'{year:04d}-{month:02d}', f'Tháng {month:02d}/{year}'))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return options


@login_required
def my_attendance(request):
    employee = _current_employee(request.user)
    today = timezone.localdate()
    today_record = None
    page_obj = None
    incomplete_records = []
    my_requests = CorrectionRequest.objects.none()
    selected_month = request.GET.get('month', f'{today.year:04d}-{today.month:02d}')

    if employee:
        today_record = Attendance.objects.filter(employee=employee, date=today).first()
        incomplete_records = Attendance.objects.filter(
            employee=employee,
            effective_check_out__isnull=True,
        ).exclude(date=today).order_by('-date')[:5]
        my_requests = CorrectionRequest.objects.filter(employee=employee).order_by('-created_at')[:10]
        queryset = Attendance.objects.filter(employee=employee)
        if selected_month:
            try:
                year, month = selected_month.split('-')
                queryset = queryset.filter(date__year=int(year), date__month=int(month))
            except (ValueError, TypeError):
                selected_month = f'{today.year:04d}-{today.month:02d}'
        page_obj = Paginator(queryset, 20).get_page(request.GET.get('page'))

    context = {
        'employee': employee,
        'today': today,
        'today_record': today_record,
        'incomplete_records': incomplete_records,
        'my_requests': my_requests,
        'page_obj': page_obj,
        'selected_month': selected_month,
        'month_options': _month_options(today),
    }
    return render(request, 'attendance/my.html', context)


@login_required
@require_POST
def check_in(request):
    employee = _current_employee(request.user)
    if not employee:
        messages.error(request, 'Tài khoản của bạn chưa gắn hồ sơ nhân viên nên chưa thể chấm công.')
        return redirect('attendance:my')

    today = timezone.localdate()
    with transaction.atomic():
        Employee.objects.select_for_update().get(pk=employee.pk)
        existing = Attendance.objects.filter(employee=employee, date=today).first()
        if existing and existing.original_check_in:
            messages.info(request, 'Hôm nay bạn đã chấm công vào rồi.')
            return redirect('attendance:my')

        now = timezone.now()
        try:
            created = Attendance.objects.create(
                employee=employee,
                date=today,
                original_check_in=now,
                effective_check_in=now,
            )
        except IntegrityError:
            messages.info(request, 'Hôm nay bạn đã chấm công vào rồi.')
            return redirect('attendance:my')

        audit_record(request.user, 'attendance.check_in', 'Attendance', created.pk, after=_attendance_snapshot(created))

    messages.success(request, 'Đã chấm công vào.')
    return redirect('attendance:my')


@login_required
@require_POST
def check_out(request):
    employee = _current_employee(request.user)
    if not employee:
        messages.error(request, 'Tài khoản của bạn chưa gắn hồ sơ nhân viên nên chưa thể chấm công.')
        return redirect('attendance:my')

    today = timezone.localdate()
    with transaction.atomic():
        Employee.objects.select_for_update().get(pk=employee.pk)
        record = Attendance.objects.filter(employee=employee, date=today).first()
        if not record or not record.original_check_in:
            messages.error(request, 'Bạn chưa chấm công vào hôm nay nên không thể chấm công ra.')
            return redirect('attendance:my')
        if record.effective_check_out:
            messages.info(request, 'Hôm nay bạn đã chấm công ra rồi.')
            return redirect('attendance:my')

        now = timezone.now()
        record.original_check_out = now
        record.effective_check_out = now
        record.save(update_fields=['original_check_out', 'effective_check_out', 'updated_at'])
        audit_record(request.user, 'attendance.check_out', 'Attendance', record.pk, after=_attendance_snapshot(record))

    messages.success(request, 'Đã chấm công ra.')
    return redirect('attendance:my')


@login_required
def correction_create(request):
    employee = _current_employee(request.user)
    if not employee:
        messages.error(request, 'Tài khoản của bạn chưa gắn hồ sơ nhân viên nên chưa thể gửi yêu cầu sửa.')
        return redirect('attendance:my')

    target_date = _parse_date(request.POST.get('date') or request.GET.get('date'))
    if not target_date:
        messages.error(request, 'Ngày cần sửa không hợp lệ.')
        return redirect('attendance:my')

    if target_date > timezone.localdate():
        messages.error(request, 'Không thể gửi yêu cầu sửa cho ngày trong tương lai.')
        return redirect('attendance:my')

    if CorrectionRequest.objects.filter(
        employee=employee,
        date=target_date,
        state=CorrectionRequest.STATE_PENDING,
    ).exists():
        messages.info(request, 'Bạn đã có một yêu cầu đang chờ duyệt cho ngày này.')
        return redirect('attendance:my')

    attendance = Attendance.objects.filter(employee=employee, date=target_date).first()

    if request.method == 'POST':
        form = CorrectionRequestForm(
            request.POST,
            date=target_date,
            joining_date=employee.joining_date,
            end_date=employee.end_date,
        )
        if form.is_valid():
            proposed_in, proposed_out = form.proposed_datetimes()
            correction = CorrectionRequest.objects.create(
                employee=employee,
                date=target_date,
                attendance=attendance,
                base_revision=attendance.revision if attendance else 0,
                proposed_check_in=proposed_in,
                proposed_check_out=proposed_out,
                reason=form.cleaned_data['reason'],
                requester=request.user,
            )
            audit_record(
                request.user,
                'correction.create',
                'CorrectionRequest',
                correction.pk,
                after={
                    'date': str(target_date),
                    'proposed_check_in': proposed_in.isoformat(),
                    'proposed_check_out': proposed_out.isoformat(),
                },
                reason=form.cleaned_data['reason'],
            )
            messages.success(request, 'Đã gửi yêu cầu sửa chấm công. Vui lòng chờ HR duyệt.')
            return redirect('attendance:my')
    else:
        initial = {}
        if attendance:
            if attendance.effective_check_in:
                initial['proposed_check_in'] = timezone.localtime(attendance.effective_check_in).time()
            if attendance.effective_check_out:
                initial['proposed_check_out'] = timezone.localtime(attendance.effective_check_out).time()
        form = CorrectionRequestForm(
            date=target_date,
            joining_date=employee.joining_date,
            end_date=employee.end_date,
            initial=initial,
        )

    context = {
        'form': form,
        'employee': employee,
        'target_date': target_date,
        'attendance': attendance,
    }
    return render(request, 'attendance/correction_form.html', context)


@hr_required
def correction_queue(request):
    state = request.GET.get('state', CorrectionRequest.STATE_PENDING)
    queryset = CorrectionRequest.objects.select_related('employee', 'requester', 'reviewer')
    if state == 'all':
        pass
    elif state in dict(CorrectionRequest.STATE_CHOICES):
        queryset = queryset.filter(state=state)
    else:
        state = CorrectionRequest.STATE_PENDING
        queryset = queryset.filter(state=CorrectionRequest.STATE_PENDING)

    page_obj = Paginator(queryset, 15).get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'selected_state': state,
        'state_choices': CorrectionRequest.STATE_CHOICES,
        'pending_count': CorrectionRequest.objects.filter(state=CorrectionRequest.STATE_PENDING).count(),
    }
    return render(request, 'attendance/correction_queue.html', context)


@hr_required
def correction_detail(request, pk):
    correction = get_object_or_404(
        CorrectionRequest.objects.select_related('employee', 'attendance', 'requester', 'reviewer'),
        pk=pk,
    )
    audit_logs = AuditLog.objects.filter(
        entity_type='CorrectionRequest',
        entity_id=correction.pk,
    ).select_related('actor')
    context = {
        'correction': correction,
        'audit_logs': audit_logs,
    }
    return render(request, 'attendance/correction_detail.html', context)


def _decision_reason(request):
    form = CorrectionDecisionForm(request.POST)
    if form.is_valid():
        return form.cleaned_data['decision_reason']
    return ''


@hr_required
@require_POST
def correction_approve(request, pk):
    with transaction.atomic():
        correction = get_object_or_404(CorrectionRequest, pk=pk)
        Employee.objects.select_for_update().get(pk=correction.employee_id)
        correction = CorrectionRequest.objects.select_for_update().get(pk=pk)

        if correction.state != CorrectionRequest.STATE_PENDING:
            messages.error(request, 'Yêu cầu này đã được xử lý.')
            return redirect('attendance:correction_detail', pk=pk)
        if correction.requester_id == request.user.id:
            messages.error(request, 'Bạn không thể tự duyệt yêu cầu sửa của chính mình.')
            return redirect('attendance:correction_detail', pk=pk)

        attendance = Attendance.objects.select_for_update().filter(
            employee_id=correction.employee_id,
            date=correction.date,
        ).first()
        current_revision = attendance.revision if attendance else 0

        if current_revision != correction.base_revision:
            correction.state = CorrectionRequest.STATE_SUPERSEDED
            correction.reviewer = request.user
            correction.decided_at = timezone.now()
            correction.decision_reason = 'Dữ liệu chấm công đã thay đổi sau khi yêu cầu được gửi.'
            correction.save(update_fields=['state', 'reviewer', 'decided_at', 'decision_reason', 'updated_at'])
            audit_record(
                request.user,
                'correction.supersede',
                'CorrectionRequest',
                correction.pk,
                before={'base_revision': correction.base_revision},
                after={'revision': current_revision},
                reason=correction.decision_reason,
            )
            messages.warning(request, 'Dữ liệu chấm công đã thay đổi từ lúc gửi yêu cầu nên yêu cầu được đánh dấu "Đã thay thế".')
            return redirect('attendance:correction_detail', pk=pk)

        before_snapshot = _attendance_snapshot(attendance)
        now = timezone.now()
        if attendance is None:
            attendance = Attendance.objects.create(
                employee_id=correction.employee_id,
                date=correction.date,
                revision=1,
                source=Attendance.SOURCE_CORRECTION,
                effective_check_in=correction.proposed_check_in,
                effective_check_out=correction.proposed_check_out,
            )
        else:
            attendance.effective_check_in = correction.proposed_check_in
            attendance.effective_check_out = correction.proposed_check_out
            attendance.revision += 1
            attendance.source = Attendance.SOURCE_CORRECTION
            attendance.save(update_fields=['effective_check_in', 'effective_check_out', 'revision', 'source', 'updated_at'])

        correction.state = CorrectionRequest.STATE_APPROVED
        correction.reviewer = request.user
        correction.decided_at = now
        correction.decision_reason = _decision_reason(request)
        correction.save(update_fields=['state', 'reviewer', 'decided_at', 'decision_reason', 'updated_at'])

        audit_record(
            request.user,
            'correction.approve',
            'CorrectionRequest',
            correction.pk,
            before=before_snapshot,
            after=_attendance_snapshot(attendance),
            reason=correction.decision_reason,
        )

    messages.success(request, 'Đã duyệt yêu cầu sửa chấm công.')
    return redirect('attendance:correction_detail', pk=pk)


@hr_required
@require_POST
def correction_reject(request, pk):
    with transaction.atomic():
        correction = get_object_or_404(CorrectionRequest, pk=pk)
        Employee.objects.select_for_update().get(pk=correction.employee_id)
        correction = CorrectionRequest.objects.select_for_update().get(pk=pk)

        if correction.state != CorrectionRequest.STATE_PENDING:
            messages.error(request, 'Yêu cầu này đã được xử lý.')
            return redirect('attendance:correction_detail', pk=pk)
        if correction.requester_id == request.user.id:
            messages.error(request, 'Bạn không thể tự xử lý yêu cầu sửa của chính mình.')
            return redirect('attendance:correction_detail', pk=pk)

        correction.state = CorrectionRequest.STATE_REJECTED
        correction.reviewer = request.user
        correction.decided_at = timezone.now()
        correction.decision_reason = _decision_reason(request)
        correction.save(update_fields=['state', 'reviewer', 'decided_at', 'decision_reason', 'updated_at'])
        audit_record(
            request.user,
            'correction.reject',
            'CorrectionRequest',
            correction.pk,
            reason=correction.decision_reason,
        )

    messages.success(request, 'Đã từ chối yêu cầu sửa chấm công.')
    return redirect('attendance:correction_detail', pk=pk)


@hr_required
def attendance_manage(request):
    selected_date = _parse_date(request.GET.get('date')) or timezone.localdate()
    department_id = request.GET.get('department', '')
    status = request.GET.get('status', '')

    employees = Employee.objects.select_related('department').order_by('employee_code')
    if department_id:
        employees = employees.filter(department_id=department_id)

    records = {
        record.employee_id: record
        for record in Attendance.objects.filter(date=selected_date, employee__in=employees)
    }

    rows = []
    for employee in employees:
        record = records.get(employee.pk)
        if record is None:
            row_status = 'none'
        elif record.effective_check_out is None:
            row_status = 'working'
        else:
            row_status = 'done'
        rows.append({'employee': employee, 'record': record, 'row_status': row_status})

    if status in ('none', 'working', 'done'):
        rows = [row for row in rows if row['row_status'] == status]

    context = {
        'selected_date': selected_date,
        'departments': Department.objects.all(),
        'selected_department': department_id,
        'selected_status': status,
        'rows': rows,
        'status_choices': [
            ('', 'Tất cả trạng thái'),
            ('none', 'Chưa chấm công'),
            ('working', 'Đang làm việc'),
            ('done', 'Đã hoàn thành'),
        ],
    }
    return render(request, 'attendance/manage.html', context)


@hr_required
def manage_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    target_date = _parse_date(request.POST.get('date') or request.GET.get('date')) or timezone.localdate()
    record = Attendance.objects.filter(employee=employee, date=target_date).first()

    if request.method == 'POST':
        form = HRAttendanceEditForm(request.POST, date=target_date)
        if form.is_valid():
            check_in, check_out = form.datetimes()
            with transaction.atomic():
                Employee.objects.select_for_update().get(pk=employee.pk)
                locked = Attendance.objects.select_for_update().filter(employee=employee, date=target_date).first()
                before = _attendance_snapshot(locked)

                if locked is None:
                    locked = Attendance.objects.create(
                        employee=employee,
                        date=target_date,
                        revision=1,
                        source=Attendance.SOURCE_HR_HISTORICAL,
                        effective_check_in=check_in,
                        effective_check_out=check_out,
                    )
                else:
                    locked.effective_check_in = check_in
                    locked.effective_check_out = check_out
                    locked.revision += 1
                    locked.source = Attendance.SOURCE_HR_HISTORICAL
                    locked.save(update_fields=['effective_check_in', 'effective_check_out', 'revision', 'source', 'updated_at'])

                audit_record(
                    request.user,
                    'attendance.hr_edit',
                    'Attendance',
                    locked.pk,
                    before=before,
                    after=_attendance_snapshot(locked),
                    reason=form.cleaned_data['reason'],
                )

            messages.success(request, 'Đã cập nhật chấm công.')
            return redirect(f"{reverse('attendance:manage')}?date={target_date:%Y-%m-%d}")
    else:
        initial = {}
        if record:
            if record.effective_check_in:
                initial['check_in'] = timezone.localtime(record.effective_check_in).time()
            if record.effective_check_out:
                initial['check_out'] = timezone.localtime(record.effective_check_out).time()
        form = HRAttendanceEditForm(date=target_date, initial=initial)

    context = {
        'form': form,
        'employee': employee,
        'target_date': target_date,
        'record': record,
    }
    return render(request, 'attendance/manage_edit.html', context)
