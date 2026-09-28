import json
import math
import os
import random
import signal
import sys
import time
import urllib.error
import urllib.request
import zlib
from collections import deque
from datetime import datetime, timezone


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return int(default)


API_BASE_URL = os.getenv("API_BASE_URL", "http://host.docker.internal:8000/api/v1").rstrip("/")
API_HOST_HEADER = os.getenv("API_HOST_HEADER", "localhost:8000")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

DISCOVERY_INTERVAL_SECONDS = _env_float("DISCOVERY_INTERVAL_SECONDS", 10)
SEND_INTERVAL_SECONDS = _env_float("SEND_INTERVAL_SECONDS", 5)
MAX_PACKETS_PER_MINUTE = _env_int("MAX_PACKETS_PER_MINUTE", 90)

SEND_FOR_STATUSES = {
    s.strip() for s in os.getenv("SEND_FOR_STATUSES", "active").split(",") if s.strip()
}

REQUIRE_DRIVER = os.getenv("REQUIRE_DRIVER", "true").strip().lower() in ("1", "true", "yes", "on")

CENTER_LAT = _env_float("START_LAT", 35.6892)
CENTER_LON = _env_float("START_LON", 51.3890)

FUEL_DROP_PER_SECOND = _env_float("FUEL_DROP_PER_SECOND", 0.008)

HTTP_TIMEOUT = 10
TOKEN_MAX_AGE_SECONDS = 25 * 60

RUNNING = True


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


class ApiClient:
    def __init__(self):
        self.token = None
        self.token_obtained_at = 0.0

    def _request(self, method, path, body=None, auth=True, query=None):
        url = f"{API_BASE_URL}{path}"
        if query:
            url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "Host": API_HOST_HEADER}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                raw = resp.read().decode() or "null"
                return resp.status, json.loads(raw), resp.headers
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:300]}
            return e.code, payload, e.headers
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            return 0, {"error": str(getattr(e, "reason", e))}, {}

    def login(self):
        status, payload, _ = self._request(
            "POST",
            "/auth/login/",
            {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            auth=False,
        )
        if status == 200 and "access_token" in payload:
            self.token = payload["access_token"]
            self.token_obtained_at = time.time()
            return True
        if status == 0:
            log(f"⏳ اتصال به بک‌اند برقرار نشد ({payload.get('error')}) — {API_BASE_URL}")
        elif status == 401:
            log("❌ ورود ناموفق: یوزرنیم/پسورد ادمین اشتباه است (ADMIN_USERNAME / ADMIN_PASSWORD).")
        else:
            log(f"❌ ورود ناموفق ({status}): {payload}")
        return False

    def ensure_login(self):
        if self.token and time.time() - self.token_obtained_at < TOKEN_MAX_AGE_SECONDS:
            return True
        return self.login()

    def call(self, method, path, body=None, query=None):
        if not self.ensure_login():
            return 0, {"error": "login failed"}, {}
        result = self._request(method, path, body, query=query)
        if result[0] == 401:
            log("⚠️  توکن نامعتبر شد، دوباره وارد می‌شویم...")
            if self.login():
                result = self._request(method, path, body, query=query)
        return result

    def list_vehicles(self):
        status, payload, _ = self.call("GET", "/vehicles/")
        if status == 200 and isinstance(payload, list):
            return payload
        if status == 200 and isinstance(payload, dict) and isinstance(payload.get("results"), list):
            return payload["results"]
        log(f"⚠️  دریافت لیست خودروها ناموفق بود ({status}): {payload}")
        return None

    def last_telemetry(self, vehicle_id):
        status, payload, _ = self.call("GET", "/telemetry/", query={"vehicle_id": vehicle_id})
        if status == 200 and isinstance(payload, list) and payload:
            return payload[0]
        return None

    def send_packet(self, packet):
        return self.call("POST", "/telemetry/", packet)


class SimulatedVehicle:
    def __init__(self, vehicle_id, obu_serial, last=None):
        self.vehicle_id = vehicle_id
        self.obu_serial = obu_serial
        self.sent_count = 0

        seed = zlib.crc32(vehicle_id.encode())
        rng = random.Random(seed)
        self.home_lat = CENTER_LAT + rng.uniform(-0.08, 0.08)
        self.home_lon = CENTER_LON + rng.uniform(-0.08, 0.08)

        if last:
            self.lat = float(last["latitude"])
            self.lon = float(last["longitude"])
            self.odometer = float(last["odometer"])
            self.fuel = float(last["fuel_level"])
            self.speed = float(last["speed"])
            self.temp = float(last["engine_temperature"])
            self.battery = float(last["battery_voltage"])
            log(f"↩️  ادامه از آخرین داده‌ی {vehicle_id} (odometer={self.odometer:.1f})")
        else:
            self.lat, self.lon = self.home_lat, self.home_lon
            self.odometer = round(rng.uniform(5_000, 90_000), 1)
            self.fuel = round(rng.uniform(60, 95), 1)
            self.speed = rng.uniform(30, 70)
            self.temp = rng.uniform(80, 92)
            self.battery = rng.uniform(13.0, 14.2)

        self.heading = random.uniform(0, 2 * math.pi)
        self.last_step_at = time.time()
        self.next_send_at = time.time() + random.uniform(0, SEND_INTERVAL_SECONDS)

    def step(self):
        now = time.time()
        dt = max(0.5, now - self.last_step_at)
        self.last_step_at = now

        self.speed = max(0.0, min(130.0, self.speed + random.uniform(-8, 8)))
        distance_km = self.speed * dt / 3600.0

        self.heading += random.uniform(-0.25, 0.25)
        d_lat = self.lat - self.home_lat
        d_lon = self.lon - self.home_lon
        if math.hypot(d_lat, d_lon) > 0.15:
            self.heading = math.atan2(-d_lon, -d_lat) + random.uniform(-0.3, 0.3)

        self.lat += distance_km * math.cos(self.heading) / 111.0
        self.lon += distance_km * math.sin(self.heading) / (111.0 * max(0.2, math.cos(math.radians(self.lat))))
        self.lat = max(-90.0, min(90.0, self.lat))
        self.lon = max(-180.0, min(180.0, self.lon))

        self.odometer += distance_km

        self.fuel -= dt * FUEL_DROP_PER_SECOND * (0.4 + self.speed / 80.0)
        if self.fuel < 8:
            self.fuel = random.uniform(85, 100)
        self.fuel = max(0.0, min(100.0, self.fuel))

        target_temp = 78 + self.speed * 0.12
        self.temp += (target_temp - self.temp) * 0.2 + random.uniform(-1.5, 1.5)
        self.temp = max(70.0, min(105.0, self.temp))

        self.battery = max(12.0, min(14.4, self.battery + random.uniform(-0.1, 0.1)))

        self.sent_count += 1
        return {
            "vehicle_id": self.vehicle_id,
            "obu_serial": self.obu_serial,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "speed": round(self.speed, 1),
            "engine_temperature": round(self.temp, 1),
            "battery_voltage": round(self.battery, 2),
            "fuel_level": round(self.fuel, 1),
            "latitude": round(self.lat, 6),
            "longitude": round(self.lon, 6),
            "odometer": round(self.odometer, 1),
        }


class RateLimiter:
    def __init__(self, per_minute):
        self.per_minute = max(1, per_minute)
        self.sent = deque()
        self.blocked_until = 0.0

    def _trim(self, now):
        while self.sent and now - self.sent[0] >= 60:
            self.sent.popleft()

    def wait_time(self):
        now = time.time()
        self._trim(now)
        wait = max(0.0, self.blocked_until - now)
        if len(self.sent) >= self.per_minute:
            wait = max(wait, 60 - (now - self.sent[0]) + 0.05)
        return wait

    def record(self):
        self.sent.append(time.time())

    def block_for(self, seconds):
        self.blocked_until = max(self.blocked_until, time.time() + seconds)


def eligible_vehicles(raw_vehicles):
    result = {}
    no_obu = []
    no_driver = []
    for v in raw_vehicles:
        vid = v.get("vehicle_id")
        if not vid:
            continue
        if v.get("status") not in SEND_FOR_STATUSES:
            continue
        obu = v.get("obu")
        if not obu or not obu.get("serial_number"):
            no_obu.append(vid)
            continue
        if obu.get("is_active") is False:
            continue
        if REQUIRE_DRIVER and not v.get("driver"):
            no_driver.append(vid)
            continue
        result[vid] = obu["serial_number"]
    return result, no_obu, no_driver


def sync_fleet(api, fleet, warned_no_obu, warned_no_driver):
    raw = api.list_vehicles()
    if raw is None:
        return

    wanted, no_obu, no_driver = eligible_vehicles(raw)

    for vid in no_obu:
        if vid not in warned_no_obu:
            warned_no_obu.add(vid)
            log(f"ℹ️  خودروی {vid} هنوز OBU ندارد؛ بعد از ثبت شماره سریال OBU شروع می‌شود.")

    for vid in no_driver:
        if vid not in warned_no_driver:
            warned_no_driver.add(vid)
            log(f"ℹ️  خودروی {vid} راننده ندارد؛ تا وقتی راننده به آن اختصاص داده نشود داده ارسال نمی‌شود.")

    for vid, serial in wanted.items():
        if vid not in fleet:
            fleet[vid] = SimulatedVehicle(vid, serial, last=api.last_telemetry(vid))
            warned_no_obu.discard(vid)
            warned_no_driver.discard(vid)
            log(f"🆕 خودروی {vid} (OBU={serial}) شروع به ارسال کرد. "
                f"مجموع خودروهای فعال: {len(fleet)}")
        elif fleet[vid].obu_serial != serial:
            log(f"🔁 سریال OBU خودروی {vid} تغییر کرد: {fleet[vid].obu_serial} → {serial}")
            fleet[vid].obu_serial = serial

    no_driver_set = set(no_driver)
    for vid in list(fleet):
        if vid not in wanted:
            del fleet[vid]
            reason = "راننده‌اش برداشته شد" if vid in no_driver_set else "دیگر فعال/موجود نیست"
            log(f"🛑 خودروی {vid} {reason} — ارسال متوقف شد. مجموع خودروهای فعال: {len(fleet)}")


def effective_interval(vehicle_count):
    if vehicle_count <= 0:
        return SEND_INTERVAL_SECONDS
    needed = vehicle_count * 60.0 / MAX_PACKETS_PER_MINUTE
    return max(SEND_INTERVAL_SECONDS, needed)


def handle_signal(signum, frame):
    global RUNNING
    RUNNING = False


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    log("== شبیه‌ساز کلی OBU ==")
    log(f"API: {API_BASE_URL} (Host header: {API_HOST_HEADER}) | ادمین: {ADMIN_USERNAME}")
    log(f"هر {SEND_INTERVAL_SECONDS:g} ثانیه برای هر خودرو | Discovery هر {DISCOVERY_INTERVAL_SECONDS:g} ثانیه | "
        f"سقف نرخ: {MAX_PACKETS_PER_MINUTE}/min | وضعیت‌های مجاز: {', '.join(sorted(SEND_FOR_STATUSES))} | "
        f"نیاز به راننده: {'بله' if REQUIRE_DRIVER else 'خیر'}")

    api = ApiClient()
    fleet = {}
    warned_no_obu = set()
    warned_no_driver = set()
    total_sent = 0
    limiter = RateLimiter(MAX_PACKETS_PER_MINUTE)

    while RUNNING and not api.login():
        time.sleep(5)
    if RUNNING:
        log("✅ وارد شدیم. منتظر خودروها...\n")

    next_discovery = 0.0
    last_interval_logged = None

    while RUNNING:
        now = time.time()

        if now >= next_discovery:
            sync_fleet(api, fleet, warned_no_obu, warned_no_driver)
            next_discovery = time.time() + DISCOVERY_INTERVAL_SECONDS

            interval = effective_interval(len(fleet))
            if interval != last_interval_logged and fleet:
                if interval > SEND_INTERVAL_SECONDS:
                    log(f"⚙️  به‌خاطر تعداد خودروها ({len(fleet)})، فاصله‌ی ارسال هر خودرو "
                        f"به {interval:.1f} ثانیه افزایش یافت (سقف {MAX_PACKETS_PER_MINUTE}/min).")
                last_interval_logged = interval

        interval = effective_interval(len(fleet))
        due = [v for v in fleet.values() if v.next_send_at <= time.time()]

        if not due:
            time.sleep(0.5)
            continue

        due.sort(key=lambda v: v.next_send_at)
        vehicle = due[0]

        wait = limiter.wait_time()
        if wait > 0:
            time.sleep(min(wait, 1.0))
            continue

        packet = vehicle.step()
        status, resp, headers = api.send_packet(packet)
        limiter.record()

        if status == 202:
            total_sent += 1
            log(f"✅ {vehicle.vehicle_id} #{vehicle.sent_count} | speed={packet['speed']} "
                f"temp={packet['engine_temperature']} fuel={packet['fuel_level']} "
                f"odo={packet['odometer']} | dispatch_id={resp.get('dispatch_id')}")
        elif status == 429:
            retry_after = 30.0
            try:
                retry_after = float(headers.get("Retry-After", retry_after))
            except (TypeError, ValueError):
                pass
            limiter.block_for(retry_after)
            log(f"⏸️  سقف نرخ بک‌اند (429) — {retry_after:.0f} ثانیه صبر می‌کنیم.")
        elif status == 503:
            limiter.block_for(5)
            log("⚠️  صف RabbitMQ موقتاً در دسترس نیست (503) — بعداً دوباره.")
        elif status == 0:
            log(f"⚠️  بک‌اند در دسترس نیست: {resp.get('error')}")
            limiter.block_for(5)
        elif status == 422:
            log(f"❌ {vehicle.vehicle_id} رد شد (422): {resp}")
        else:
            log(f"❌ {vehicle.vehicle_id} خطا ({status}): {resp}")

        vehicle.next_send_at = time.time() + interval

    log(f"\nمتوقف شد. مجموعاً {total_sent} بسته ارسال شد.")


if __name__ == "__main__":
    sys.exit(main())