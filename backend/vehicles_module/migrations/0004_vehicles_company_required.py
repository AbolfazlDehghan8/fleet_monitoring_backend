import django.db.models.deletion
from django.db import migrations, models


def backfill_vehicle_company(apps, schema_editor):
    Company = apps.get_model('vehicles_module', 'Company')
    Vehicle = apps.get_model('vehicles_module', 'Vehicle')

    company = Company.objects.first()
    if company is None:
        company = Company.objects.create(name='Default Company')

    Vehicle.objects.filter(company__isnull=True).update(company=company)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles_module', '0003_seed_company'),
    ]

    operations = [
        migrations.RunPython(backfill_vehicle_company, noop_reverse),
        migrations.AlterField(
            model_name='vehicle',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vehicles',
                to='vehicles_module.company',
            ),
        ),
    ]