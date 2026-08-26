import logging
import time
from contextlib import contextmanager

from .middleware import get_correlation_id

tracer_logger = logging.getLogger('audit')


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
    try:
        yield
    except Exception:
        status = 'error'
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