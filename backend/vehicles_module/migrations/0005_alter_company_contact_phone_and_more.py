import re

import django.core.validators
from django.db import migrations, models


def _normalize_phone(raw, max_len):
    """Best-effort cleanup so old free-form numbers fit the new column size."""
    if not raw:
        return raw
    value = re.sub(r'[\s\-()]', '', raw)
    if value.startswith('+98'):
        value = '0' + value[3:]
    elif value.startswith('0098'):
        value = '0' + value[4:]
    elif value.startswith('98') and len(value) > 10:
        value = '0' + value[2:]
    # Still too long for the new column? Truncate as a last resort so the
    # migration can run; these rows should be reviewed manually afterwards.
    return value[:max_len]


def _normalize_plate(raw, max_len):
    if not raw:
        return raw
    value = re.sub(r'[\s\-]', '', raw)
    return value[:max_len]


def normalize_existing_data(apps, schema_editor):
    Company = apps.get_model('vehicles_module', 'Company')
    Driver = apps.get_model('vehicles_module', 'Driver')
    Vehicle = apps.get_model('vehicles_module', 'Vehicle')

    for company in Company.objects.exclude(contact_phone=''):
        cleaned = _normalize_phone(company.contact_phone, 11)
        if cleaned != company.contact_phone:
            company.contact_phone = cleaned
            company.save(update_fields=['contact_phone'])

    for driver in Driver.objects.exclude(phone_number=''):
        cleaned = _normalize_phone(driver.phone_number, 11)
        if cleaned != driver.phone_number:
            driver.phone_number = cleaned
            driver.save(update_fields=['phone_number'])

    for vehicle in Vehicle.objects.all():
        cleaned = _normalize_plate(vehicle.license_plate, 8)
        if cleaned != vehicle.license_plate:
            vehicle.license_plate = cleaned
            vehicle.save(update_fields=['license_plate'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles_module', '0004_vehicles_company_required'),
    ]

    operations = [
        migrations.RunPython(normalize_existing_data, noop_reverse),
        migrations.AlterField(
            model_name='company',
            name='contact_phone',
            field=models.CharField(blank=True, max_length=11, validators=[django.core.validators.RegexValidator(code='invalid_iran_phone', message='شماره تلفن باید مطابق فرمت ایران و به\u200cصورت ۱۱ رقم و با 0 شروع شود. مثال: 09123456789 یا 02112345678', regex='^0\\d{10}$')]),
        ),
        migrations.AlterField(
            model_name='driver',
            name='phone_number',
            field=models.CharField(blank=True, max_length=11, validators=[django.core.validators.RegexValidator(code='invalid_iran_mobile', message='شماره موبایل باید مطابق فرمت ایران و به\u200cصورت ۱۱ رقم و با 09 شروع شود. مثال: 09123456789', regex='^09\\d{9}$')]),
        ),
        migrations.AlterField(
            model_name='vehicle',
            name='license_plate',
            field=models.CharField(max_length=8, unique=True, validators=[django.core.validators.RegexValidator(code='invalid_iran_plate', message='شماره پلاک باید مطابق فرمت پلاک ایران باشد: دو رقم + یک حرف فارسی + سه رقم + دو رقم (کد شهر). مثال: 12ب34567', regex='^\\d{2}(الف|ب|پ|ت|ث|ج|د|ز|س|ش|ص|ط|ع|ف|ق|ک|گ|ل|م|ن|و|ه|ی)\\d{3}\\d{2}$')]),
        ),
    ]