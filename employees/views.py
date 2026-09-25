from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import hr_required

from .forms import AccountProvisionForm, DepartmentForm, EmployeeForm
from .models import Department, Employee


User = get_user_model()


@hr_required
def employee_list(request):
    employees = Employee.objects.select_related('department', 'user')

    query = request.GET.get('q', '').strip()
    department_id = request.GET.get('department', '')
    status = request.GET.get('status', '')

    if query:
        employees = employees.filter(full_name__icontains=query) | employees.filter(employee_code__icontains=query)
    if department_id:
        employees = employees.filter(department_id=department_id)
    if status == 'active':
        employees = employees.filter(is_active=True)
    elif status == 'inactive':
        employees = employees.filter(is_active=False)

    paginator = Paginator(employees, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'departments': Department.objects.all(),
        'query': query,
        'selected_department': department_id,
        'selected_status': status,
        'total_count': employees.count(),
    }
    return render(request, 'employees/employee_list.html', context)


@hr_required
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Đã thêm nhân viên {employee.full_name} ({employee.employee_code}).')
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = EmployeeForm()
    return render(request, 'employees/employee_form.html', {'form': form, 'is_create': True})


@hr_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee.objects.select_related('department', 'user'), pk=pk)
    return render(request, 'employees/employee_detail.html', {'employee': employee})


@hr_required
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã cập nhật hồ sơ nhân viên.')
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'employees/employee_form.html', {'form': form, 'employee': employee, 'is_create': False})


@hr_required
@require_POST
def employee_deactivate(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if not employee.is_active:
        messages.info(request, 'Nhân viên đã ở trạng thái ngừng làm việc.')
        return redirect('employees:detail', pk=employee.pk)

    employee.is_active = False
    if not employee.end_date:
        employee.end_date = timezone.localdate()
    employee.save()

    if employee.user:
        employee.user.is_active = False
        employee.user.save(update_fields=['is_active'])

    messages.success(request, f'Đã vô hiệu hóa {employee.full_name}. Lịch sử dữ liệu vẫn được giữ lại.')
    return redirect('employees:detail', pk=employee.pk)


@hr_required
def employee_provision_account(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    if employee.user:
        messages.info(request, 'Nhân viên này đã có tài khoản đăng nhập.')
        return redirect('employees:detail', pk=employee.pk)

    if request.method == 'POST':
        form = AccountProvisionForm(request.POST, employee=employee)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                role=User.ROLE_EMPLOYEE,
                email=employee.work_email,
                is_active=employee.is_active,
            )
            employee.user = user
            employee.save(update_fields=['user'])
            messages.success(request, f'Đã cấp tài khoản "{user.username}" cho {employee.full_name}.')
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = AccountProvisionForm(employee=employee)

    return render(request, 'employees/account_form.html', {'form': form, 'employee': employee})


@hr_required
def department_list(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(request, f'Đã thêm phòng ban {department.name}.')
            return redirect('employees:department_list')
    else:
        form = DepartmentForm()

    context = {
        'form': form,
        'departments': Department.objects.all(),
    }
    return render(request, 'employees/department_list.html', context)


@hr_required
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã cập nhật phòng ban.')
            return redirect('employees:department_list')
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'employees/department_form.html', {'form': form, 'department': department})


@hr_required
@require_POST
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if department.employees.exists():
        messages.error(request, 'Không thể xóa phòng ban đang có nhân viên. Hãy chuyển nhân viên sang phòng ban khác trước.')
        return redirect('employees:department_list')

    name = department.name
    department.delete()
    messages.success(request, f'Đã xóa phòng ban {name}.')
    return redirect('employees:department_list')
