FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app


COPY obu_fleet_simulator.py .

RUN useradd --create-home --uid 1000 obu
USER obu

CMD ["python", "obu_fleet_simulator.py"]
