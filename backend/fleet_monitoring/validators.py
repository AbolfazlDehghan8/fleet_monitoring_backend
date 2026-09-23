import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

from .persian import is_valid_iran_national_code

iran_mobile_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='شماره موبایل باید به‌صورت ۱۱ رقم و با 09 شروع شود. مثال: 09123456789',
    code='invalid_iran_mobile',
)

iran_phone_validator = RegexValidator(
    regex=r'^0\d{10}$',
    message='شماره تلفن باید به‌صورت ۱۱ رقم و با 0 شروع شود. مثال: 09123456789 یا 02112345678',
    code='invalid_iran_phone',
)

_IRAN_PLATE_LETTERS = (
    'الف|ب|پ|ت|ث|ج|د|ز|س|ش|ص|ط|ع|ف|ق|ک|گ|ل|م|ن|و|ه|ی'
)
iran_plate_validator = RegexValidator(
    regex=r'^\d{2}(' + _IRAN_PLATE_LETTERS + r')\d{3}\d{2}$',
    message=(
        'شماره پلاک باید مطابق فرمت پلاک ایران باشد: دو رقم + یک حرف فارسی + '
        'سه رقم + دو رقم (کد شهر). مثال: 12ب34567'
    ),
    code='invalid_iran_plate',
)

vin_validator = RegexValidator(
    regex=r'^[A-HJ-NPR-Z0-9]{17}$',
    message='شماره شاسی (VIN) باید ۱۷ کاراکتر شامل حروف انگلیسی و اعداد باشد (بدون I، O یا Q). مثال: 1HGCM82633A004352',
    code='invalid_vin',
    flags=re.IGNORECASE,
)

obu_serial_validator = RegexValidator(
    regex=r'^OBU-\d{4}-\d{4,}$',
    message='شماره سریال OBU باید با فرمت OBU-YYYY-NNNN باشد. مثال: OBU-2026-0001',
    code='invalid_obu_serial',
    flags=re.IGNORECASE,
)

iran_driver_license_validator = RegexValidator(
    regex=r'^\d{10}$',
    message='شماره گواهینامه باید دقیقاً ۱۰ رقم باشد.',
    code='invalid_iran_license_number',
)


def iran_national_code_validator(value):
    if not is_valid_iran_national_code(value):
        raise ValidationError(
            'کد ملی نامعتبر است. کد ملی باید ۱۰ رقم و دارای ارقام کنترلی صحیح باشد.',
            code='invalid_iran_national_code',
        )


_VEHICLE_ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,49}')


def validate_vehicle_id(value):
    if not _VEHICLE_ID_RE.fullmatch(value or ''):
        raise ValidationError(
            'شناسه خودرو فقط می‌تواند شامل حروف انگلیسی، عدد و . _ - باشد (حداکثر ۵۰ کاراکتر). مثال: veh_8a3f2b1c',
            code='invalid_vehicle_id',
        )


def validate_vehicle_year(value):
    max_gregorian = timezone.now().year + 1
    if not (1330 <= value <= 1420 or 1950 <= value <= max_gregorian):
        raise ValidationError(
            f'سال ساخت نامعتبر است (سال شمسی ۱۳۳۰ تا ۱۴۲۰ یا سال میلادی ۱۹۵۰ تا {max_gregorian}).',
            code='invalid_vehicle_year',
        )