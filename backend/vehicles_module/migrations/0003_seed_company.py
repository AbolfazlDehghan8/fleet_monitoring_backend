from django.db import migrations


def seed_company(apps, schema_editor):
    Company = apps.get_model('vehicles_module', 'Company')
    if not Company.objects.exists():
        Company.objects.create(name='Default Company')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles_module', '0002_company_vehicle_company'),
    ]

    operations = [
        migrations.RunPython(seed_company, noop_reverse),
    ]