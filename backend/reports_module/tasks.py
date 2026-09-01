import logging

from celery import shared_task

logger = logging.getLogger('audit')


@shared_task(bind=True, max_retries=3, default_retry_delay=15, retry_backoff=True, queue='reports.generate')
def generate_report_task(self, report_id):
    from .services import ReportService

    try:
        ReportService.run_report(report_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(queue='reports.generate')
def generate_scheduled_fleet_report():
    from .models import Report

    report = Report.objects.create(requested_by=None, status=Report.Status.PENDING)
    generate_report_task.apply_async(args=[report.id], queue='reports.generate')

    logger.info(
        'scheduled_report_queued',
        extra={'actor': 'scheduler', 'action': 'generate_scheduled_fleet_report', 'target': str(report.id)},
    )
    return report.id