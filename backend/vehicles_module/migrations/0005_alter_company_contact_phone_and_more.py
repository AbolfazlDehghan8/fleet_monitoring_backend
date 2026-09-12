import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles_module', '0004_vehicles_company_required'),
    ]

    operations = [
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