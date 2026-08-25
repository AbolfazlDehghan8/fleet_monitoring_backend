import csv
import io
import logging
from datetime import timedelta

from django.db.models import Avg, DurationField, ExpressionWrapper, F, Max, Min
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from alerts_module.models import Alert
from telemetry_module.models import TelemetryLog
from vehicles_module.models import Vehicle

from .models import Report

DEFAULT_PERIOD_DAYS = 30

audit_logger = logging.getLogger('audit')


class ReportService:

    @staticmethod
    def _scoped_vehicles(user):
        if user.role == 'admin':
            return Vehicle.objects.all()
        if user.role == 'fleet_manager':
            return Vehicle.objects.filter(assigned_manager=user)
        return Vehicle.objects.none()

    @staticmethod
    def generate_fleet_summary(user, start_date=None, end_date=None, vehicle_id=None):
        end_date = end_date or timezone.now()
        start_date = start_date or (end_date - timedelta(days=DEFAULT_PERIOD_DAYS))

        vehicles = ReportService._scoped_vehicles(user)
        if vehicle_id:
            vehicles = vehicles.filter(vehicle_id=vehicle_id)

        status_counts = {}
        for vehicle_status in vehicles.values_list('status', flat=True):
            status_counts[vehicle_status] = status_counts.get(vehicle_status, 0) + 1

        telemetry_qs = TelemetryLog.objects.filter(
            vehicle__in=vehicles, timestamp__gte=start_date, timestamp__lte=end_date,
        )
        total_readings = telemetry_qs.count()
        avg_speed = telemetry_qs.aggregate(avg=Avg('speed'))['avg']
        avg_fuel_level = telemetry_qs.aggregate(avg=Avg('fuel_level'))['avg']

        distance_traveled_km = 0.0
        odometer_bounds = telemetry_qs.values('vehicle').annotate(
            min_odo=Min('odometer'), max_odo=Max('odometer'),
        )
        for row in odometer_bounds:
            distance_traveled_km += (row['max_odo'] or 0) - (row['min_odo'] or 0)

        alerts_qs = Alert.objects.filter(
            vehicle__in=vehicles, created_at__gte=start_date, created_at__lte=end_date,
        )
        alerts_by_severity = {}
        for severity in alerts_qs.values_list('severity', flat=True):
            alerts_by_severity[severity] = alerts_by_severity.get(severity, 0) + 1

        acknowledged_qs = alerts_qs.filter(acknowledged=True, acknowledged_at__isnull=False)
        avg_ack_seconds = acknowledged_qs.annotate(
            response_time=ExpressionWrapper(
                F('acknowledged_at') - F('created_at'), output_field=DurationField(),
            )
        ).aggregate(avg=Avg('response_time'))['avg']

        return {
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'vehicle_count': vehicles.count(),
            'vehicles_by_status': status_counts,
            'telemetry': {
                'total_readings': total_readings,
                'avg_speed': round(avg_speed, 2) if avg_speed is not None else None,
                'avg_fuel_level': round(avg_fuel_level, 2) if avg_fuel_level is not None else None,
                'distance_traveled_km': round(distance_traveled_km, 2),
            },
            'alerts': {
                'total': alerts_qs.count(),
                'by_severity': alerts_by_severity,
                'acknowledged': acknowledged_qs.count(),
                'unacknowledged': alerts_qs.filter(acknowledged=False).count(),
                'avg_acknowledgment_time_seconds': (
                    round(avg_ack_seconds.total_seconds(), 1) if avg_ack_seconds is not None else None
                ),
            },
        }

    @staticmethod
    def create_pending_report(user, start_date=None, end_date=None, vehicle_id=None):
        report = Report.objects.create(
            requested_by=user,
            vehicle_id=vehicle_id or '',
            period_start=start_date,
            period_end=end_date,
            status=Report.Status.PENDING,
        )

        from .tasks import generate_report_task
        generate_report_task.apply_async(args=[report.id], queue='reports.generate')

        audit_logger.info(
            'report_requested',
            extra={'actor': user.id if user else 'system', 'action': 'request_report', 'target': str(report.id)},
        )
        return report

    @staticmethod
    def run_report(report_id):
        report = Report.objects.get(id=report_id)
        report.status = Report.Status.RUNNING
        report.save(update_fields=['status'])

        try:
            scope_user = report.requested_by
            if scope_user is not None:
                result = ReportService.generate_fleet_summary(
                    scope_user,
                    start_date=report.period_start,
                    end_date=report.period_end,
                    vehicle_id=report.vehicle_id or None,
                )
            else:
                result = ReportService._generate_system_wide_summary(
                    start_date=report.period_start, end_date=report.period_end,
                )

            report.result = result
            report.status = Report.Status.COMPLETED
            report.completed_at = timezone.now()
            report.save(update_fields=['result', 'status', 'completed_at'])

            audit_logger.info(
                'report_completed',
                extra={'actor': 'scheduler', 'action': 'generate_report', 'target': str(report.id)},
            )
        except Exception as exc:
            report.status = Report.Status.FAILED
            report.error_message = str(exc)[:500]
            report.completed_at = timezone.now()
            report.save(update_fields=['status', 'error_message', 'completed_at'])
            raise

        return report

    @staticmethod
    def _generate_system_wide_summary(start_date=None, end_date=None):
        end_date = end_date or timezone.now()
        start_date = start_date or (end_date - timedelta(days=DEFAULT_PERIOD_DAYS))

        vehicles = Vehicle.objects.all()
        status_counts = {}
        for vehicle_status in vehicles.values_list('status', flat=True):
            status_counts[vehicle_status] = status_counts.get(vehicle_status, 0) + 1

        alerts_qs = Alert.objects.filter(created_at__gte=start_date, created_at__lte=end_date)

        return {
            'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
            'vehicle_count': vehicles.count(),
            'vehicles_by_status': status_counts,
            'alerts': {'total': alerts_qs.count()},
        }

    @staticmethod
    def get_report(user, report_id):
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return None

        if user.role != 'admin' and report.requested_by_id != user.id:
            raise PermissionDenied('This report was not requested by you')

        return report

    @staticmethod
    def list_reports(user):
        if user.role == 'admin':
            return Report.objects.all()[:200]
        return Report.objects.filter(requested_by=user)[:200]

    @staticmethod
    def to_csv(report):
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        result = report.result or {}
        writer.writerow(['section', 'key', 'value'])

        def _write_section(section_name, data):
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            writer.writerow([section_name, f'{key}.{sub_key}', sub_value])
                    else:
                        writer.writerow([section_name, key, value])
            else:
                writer.writerow(['summary', section_name, data])

        for section_name, data in result.items():
            _write_section(section_name, data)

        return buffer.getvalue().encode('utf-8')