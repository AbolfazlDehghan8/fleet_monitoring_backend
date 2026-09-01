import logging
import time
from contextlib import contextmanager

from .middleware import get_correlation_id

tracer_logger = logging.getLogger('audit')


@contextmanager
def _current_or_noop_span(stage):
    tracer = None
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer('fleet_monitoring')
    except Exception:
        tracer = None

    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(stage) as span:
        yield span


@contextmanager
def trace_span(stage, **extra_fields):
    start = time.monotonic()
    correlation_id = get_correlation_id()

    tracer_logger.info(
        'span_start',
        extra={
            'actor': 'tracer',
            'action': stage,
            'target': correlation_id,
            **extra_fields,
        },
    )

    status = 'ok'
    with _current_or_noop_span(stage) as span:
        if span is not None:
            try:
                span.set_attribute('correlation_id', correlation_id)
                for key, value in extra_fields.items():
                    span.set_attribute(key, str(value))
            except Exception:
                pass
        try:
            yield span
        except Exception as exc:
            status = 'error'
            if span is not None:
                try:
                    from opentelemetry.trace import Status, StatusCode
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                except Exception:
                    pass
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            tracer_logger.info(
                'span_end',
                extra={
                    'actor': 'tracer',
                    'action': stage,
                    'target': correlation_id,
                    'status': status,
                    'duration_ms': duration_ms,
                    **extra_fields,
                },
            )