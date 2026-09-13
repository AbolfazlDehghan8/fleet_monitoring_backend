import re

from django.core.validators import RegexValidator

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