from datetime import date

from django.db import migrations


def _month_bounds(months_back=6, months_forward=12):
    today = date.today()
    start_year = today.year
    start_month = today.month - months_back
    while start_month <= 0:
        start_month += 12
        start_year -= 1

    bounds = []
    year, month = start_year, start_month
    total_months = months_back + months_forward + 1
    for _ in range(total_months):
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        bounds.append((year, month, next_year, next_month))
        year, month = next_year, next_month
    return bounds


def _partition_ddl():
    statements = []
    for year, month, next_year, next_month in _month_bounds():
        partition_name = f"telemetry_logs_{year:04d}_{month:02d}"
        statements.append(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF telemetry_logs
            FOR VALUES FROM ('{year:04d}-{month:02d}-01') TO ('{next_year:04d}-{next_month:02d}-01');
            """
        )
    return "\n".join(statements)


PARTITION_SQL = f"""
ALTER TABLE telemetry_logs RENAME TO telemetry_logs_legacy;

CREATE TABLE telemetry_logs (
    id BIGINT NOT NULL,
    obu_serial VARCHAR(50) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    speed DOUBLE PRECISION NOT NULL,
    engine_temperature DOUBLE PRECISION NOT NULL,
    battery_voltage DOUBLE PRECISION NOT NULL,
    fuel_level DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    odometer DOUBLE PRECISION NOT NULL,
    raw_payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    vehicle_id BIGINT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    PRIMARY KEY (id, "timestamp")
) PARTITION BY RANGE ("timestamp");

CREATE SEQUENCE telemetry_logs_id_seq_new;
ALTER TABLE telemetry_logs
    ALTER COLUMN id SET DEFAULT nextval('telemetry_logs_id_seq_new'::regclass);
ALTER SEQUENCE telemetry_logs_id_seq_new OWNED BY telemetry_logs.id;
SELECT setval('telemetry_logs_id_seq_new', COALESCE((SELECT MAX(id) FROM telemetry_logs_legacy), 1));

{_partition_ddl()}
CREATE TABLE IF NOT EXISTS telemetry_logs_default PARTITION OF telemetry_logs DEFAULT;

INSERT INTO telemetry_logs
SELECT id, obu_serial, "timestamp", speed, engine_temperature, battery_voltage,
       fuel_level, latitude, longitude, odometer, raw_payload, received_at, vehicle_id
FROM telemetry_logs_legacy;

DROP TABLE telemetry_logs_legacy;

ALTER SEQUENCE telemetry_logs_id_seq_new RENAME TO telemetry_logs_id_seq;

CREATE INDEX telemetry_l_vehicle_5a51ed_idx ON telemetry_logs (vehicle_id, "timestamp" DESC);
CREATE INDEX telemetry_l_timesta_f01c13_idx ON telemetry_logs ("timestamp");
ALTER TABLE telemetry_logs
    ADD CONSTRAINT uniq_telemetry_vehicle_timestamp UNIQUE (vehicle_id, "timestamp");
"""

REVERSE_SQL = """
ALTER TABLE telemetry_logs RENAME TO telemetry_logs_partitioned;

CREATE TABLE telemetry_logs (
    id BIGSERIAL PRIMARY KEY,
    obu_serial VARCHAR(50) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    speed DOUBLE PRECISION NOT NULL,
    engine_temperature DOUBLE PRECISION NOT NULL,
    battery_voltage DOUBLE PRECISION NOT NULL,
    fuel_level DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    odometer DOUBLE PRECISION NOT NULL,
    raw_payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    vehicle_id BIGINT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    CONSTRAINT uniq_telemetry_vehicle_timestamp UNIQUE (vehicle_id, "timestamp")
);
CREATE INDEX telemetry_l_vehicle_5a51ed_idx ON telemetry_logs (vehicle_id, "timestamp" DESC);
CREATE INDEX telemetry_l_timesta_f01c13_idx ON telemetry_logs ("timestamp");

INSERT INTO telemetry_logs
SELECT id, obu_serial, "timestamp", speed, engine_temperature, battery_voltage,
       fuel_level, latitude, longitude, odometer, raw_payload, received_at, vehicle_id
FROM telemetry_logs_partitioned;

DROP TABLE telemetry_logs_partitioned;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('telemetry_module', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(sql=PARTITION_SQL, reverse_sql=REVERSE_SQL),
    ]