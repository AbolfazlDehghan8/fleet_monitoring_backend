from rest_framework import serializers

from .persian import normalize_persian_text


class NormalizedCharField(serializers.CharField):

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = normalize_persian_text(data)
        return super().to_internal_value(data)