from .models import AuditLog


def record(actor, action, entity_type, entity_id, before=None, after=None, reason=''):
    return AuditLog.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        reason=reason or '',
    )
