import logging
import os

logger = logging.getLogger('fleet_monitoring.tracing_setup')

_configured = False


def tracing_enabled():
    return os.getenv('OTEL_TRACING_ENABLED', 'True').lower() in ('1', 'true', 'yes')


def setup_tracing(service_name):
    global _configured
    if _configured:
        return
    _configured = True

    if not tracing_enabled():
        logger.info('OpenTelemetry tracing disabled (OTEL_TRACING_ENABLED=False)')
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.warning(
            'opentelemetry SDK not installed; distributed tracing disabled. '
            'Install the opentelemetry-* packages from requirements.txt to enable it.'
        )
        return

    sample_ratio = float(os.getenv('OTEL_TRACES_SAMPLER_RATIO', '1.0'))

    resource = Resource.create({
        'service.name': service_name,
        'service.version': os.getenv('SERVICE_VERSION', '1.0.0'),
        'deployment.environment': os.getenv('DEPLOYMENT_ENVIRONMENT', 'development'),
    })

    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(sample_ratio)),
    )

    otlp_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info('OpenTelemetry OTLP exporter configured for %s', otlp_endpoint)
        except Exception:
            logger.exception('Failed to configure OTLP span exporter at %s', otlp_endpoint)
    else:
        logger.warning(
            'OTEL_EXPORTER_OTLP_ENDPOINT is not set; spans will be generated '
            'but not exported to a collector.'
        )

    if os.getenv('OTEL_CONSOLE_EXPORT', 'False').lower() in ('1', 'true', 'yes'):
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    _safe_instrument('django', _instrument_django)
    _safe_instrument('psycopg2', _instrument_psycopg2)
    _safe_instrument('redis', _instrument_redis)
    _safe_instrument('celery', _instrument_celery)

    logger.info('OpenTelemetry tracing initialized for service=%s', service_name)


def _safe_instrument(label, fn):
    try:
        fn()
    except Exception:
        logger.exception('Failed to instrument %s for tracing', label)


def _instrument_django():
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    DjangoInstrumentor().instrument()


def _instrument_psycopg2():
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    Psycopg2Instrumentor().instrument(skip_dep_check=True)


def _instrument_redis():
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    RedisInstrumentor().instrument()


def _instrument_celery():
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    CeleryInstrumentor().instrument()


def get_tracer():
    from opentelemetry import trace
    return trace.get_tracer('fleet_monitoring')