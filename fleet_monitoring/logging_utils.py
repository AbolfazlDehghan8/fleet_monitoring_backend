import json
import logging

from .middleware import get_correlation_id

_EXTRA_FIELDS = ('actor', 'action', 'target', 'status', 'duration_ms')
_STANDARD_LOGRECORD_ATTRS = frozenset(logging.LogRecord(
    '', 0, '', 0, '', (), None,
).__dict__.keys()) | {'correlation_id', 'message'}


class CorrelationIdFilter(logging.Filter):

    def filter(self, record):
        if not getattr(record, 'correlation_id', None):
            record.correlation_id = get_correlation_id()
        return True


class JsonFormatter(logging.Formatter):

    def format(self, record):
        payload = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', '-'),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOGRECORD_ATTRS and key not in _EXTRA_FIELDS:
                payload[key] = value
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload)