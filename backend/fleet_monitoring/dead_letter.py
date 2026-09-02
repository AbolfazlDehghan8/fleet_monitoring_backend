import json
import logging

import kombu
from django.conf import settings

logger = logging.getLogger('audit')


def publish_to_dead_letter(source_queue, task_name, payload, reason):
    body = {
        'source_queue': source_queue,
        'task_name': task_name,
        'reason': str(reason),
        'payload': payload,
    }
    try:
        with kombu.Connection(settings.CELERY_BROKER_URL) as connection:
            producer = connection.Producer(serializer='json')
            producer.publish(
                body,
                exchange=kombu.Exchange('fleet.dlx', type='direct', durable=True),
                routing_key='tasks.dead_letter',
                declare=[
                    kombu.Queue(
                        'tasks.dead_letter', durable=True,
                        queue_arguments={'x-queue-type': 'classic'},
                    )
                ],
                retry=True,
            )
        logger.error(
            'task_moved_to_dead_letter',
            extra={'actor': 'celery_worker', 'action': 'dead_letter', 'target': task_name},
        )
    except Exception:
        logger.exception(
            'dead_letter_publish_failed',
            extra={'actor': 'celery_worker', 'action': 'dead_letter_failed', 'target': task_name},
        )