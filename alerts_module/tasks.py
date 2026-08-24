import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from django.core.mail import send_mail

from fleet_monitoring.dead_letter import publish_to_dead_letter

logger = logging.getLogger('audit')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    retry_backoff_max=120,
    queue='alerts.trigger.notify',
)
def dispatch_alert_notification(self, alert_id):
    from auth_module.models import User

    from .models import Alert

    try:
        alert = Alert.objects.select_related('vehicle', 'vehicle__assigned_manager').get(id=alert_id)
    except Alert.DoesNotExist:
        logger.warning(
            'alert_notification_skipped_not_found',
            extra={'actor': 'notification_service', 'action': 'send_alert_notification', 'target': str(alert_id)},
        )
        return

    recipients = set()
    manager = alert.vehicle.assigned_manager
    if manager and manager.email:
        recipients.add(manager.email)
    admin_emails = User.objects.filter(role='admin', is_active=True).exclude(email='').values_list('email', flat=True)
    recipients.update(admin_emails)

    if not recipients:
        logger.warning(
            'alert_notification_skipped_no_recipients',
            extra={'actor': 'notification_service', 'action': 'send_alert_notification', 'target': alert.vehicle.vehicle_id},
        )
        return

    subject = f'[Fleet Alert - {alert.severity.upper()}] {alert.rule_name} on {alert.vehicle.vehicle_id}'
    message = (
        f"Vehicle: {alert.vehicle.vehicle_id}\n"
        f"Rule: {alert.rule_name}\n"
        f"Metric: {alert.metric} | Value: {alert.value} | Threshold: {alert.threshold}\n"
        f"Severity: {alert.severity}\n"
        f"Triggered at: {alert.created_at.isoformat()}\n"
    )

    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, list(recipients), fail_silently=False)
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            publish_to_dead_letter(
                source_queue='alerts.trigger.notify',
                task_name=self.name,
                payload={'alert_id': alert_id, 'recipients': list(recipients)},
                reason=f'Retries exhausted: {exc}',
            )
            raise
        return

    logger.info(
        'alert_notification_sent',
        extra={'actor': 'notification_service', 'action': 'send_alert_notification', 'target': alert.vehicle.vehicle_id},
    )