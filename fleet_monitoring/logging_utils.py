import json
import logging

from .middleware import get_correlation_id

_EXTRA_FIELDS = ('actor', 'action', 'target')


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
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload)