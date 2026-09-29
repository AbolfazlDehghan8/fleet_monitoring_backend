FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

RUN useradd --create-home --uid 1000 obu

COPY --chown=obu:obu obu_fleet_simulator.py .

USER obu

CMD ["python", "obu_fleet_simulator.py"]