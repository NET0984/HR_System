from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounts.views import hr_required

from .models import AuditLog


ENTITY_URLS = {
    'CorrectionRequest': lambda pk: reverse('attendance:correction_detail', args=[pk]),
    'LeaveRequest': lambda pk: reverse('leave:detail', args=[pk]),
}


@hr_required
def audit_list(request):
    queryset = AuditLog.objects.select_related('actor')
    action = request.GET.get('action', '')
    entity_type = request.GET.get('entity_type', '')
    if action:
        queryset = queryset.filter(action=action)
    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)

    page_obj = Paginator(queryset, 25).get_page(request.GET.get('page'))
    action_values = AuditLog.objects.order_by('action').values_list('action', flat=True).distinct()
    entity_values = AuditLog.objects.order_by('entity_type').values_list('entity_type', flat=True).distinct()
    context = {
        'page_obj': page_obj,
        'selected_action': action,
        'selected_entity': entity_type,
        'actions': [(value, AuditLog.ACTION_LABELS.get(value, value)) for value in action_values],
        'entities': [(value, AuditLog.ENTITY_LABELS.get(value, value)) for value in entity_values],
    }
    return render(request, 'audit/audit_list.html', context)


@hr_required
def audit_detail(request, pk):
    log = get_object_or_404(AuditLog.objects.select_related('actor'), pk=pk)
    entity_url_builder = ENTITY_URLS.get(log.entity_type)
    context = {
        'log': log,
        'entity_url': entity_url_builder(log.entity_id) if entity_url_builder else None,
    }
    return render(request, 'audit/audit_detail.html', context)
