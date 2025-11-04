from django.db import migrations
import uuid

def seed_status_and_events(apps, schema_editor):
    Status = apps.get_model('core', 'Status')
    Event = apps.get_model('core', 'Event')

    # 1. Create base Status records
    statuses = [
        {"id": uuid.uuid4(), "name_es": "Activo", "name_en": "Active", "abbreviation": "ACT"},
        {"id": uuid.uuid4(), "name_es": "Inactivo", "name_en": "Inactive", "abbreviation": "INA"},
        {"id": uuid.uuid4(), "name_es": "Eliminado", "name_en": "Deleted", "abbreviation": "DEL"},
    ]

    created_statuses = {}
    for status_data in statuses:
        obj, created = Status.objects.get_or_create(
            abbreviation=status_data["abbreviation"],
            defaults=status_data
        )
        created_statuses[status_data["abbreviation"]] = obj

    # 2. Create base Event records (linked to Status “Active”)
    events = [
        {"id": uuid.uuid4(), "name_es": "Creación", "name_en": "Create", "abbreviation": "CRT", "key_status": created_statuses["ACT"]},
        {"id": uuid.uuid4(), "name_es": "Actualización", "name_en": "Update", "abbreviation": "UPD", "key_status": created_statuses["ACT"]},
        {"id": uuid.uuid4(), "name_es": "Eliminación", "name_en": "Delete", "abbreviation": "DEL", "key_status": created_statuses["ACT"]},
    ]

    for event_data in events:
        Event.objects.get_or_create(
            abbreviation=event_data["abbreviation"],
            defaults=event_data
        )


def unseed_status_and_events(apps, schema_editor):
    Status = apps.get_model('core', 'Status')
    Event = apps.get_model('core', 'Event')

    # Remove only the seeded records
    Event.objects.filter(abbreviation__in=["CRT", "UPD", "DEL"]).delete()
    Status.objects.filter(abbreviation__in=["ACT", "INA", "DEL"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alter_country_unique_together_and_more'),  # Depends on your latest migration
    ]

    operations = [
        migrations.RunPython(seed_status_and_events, unseed_status_and_events),
    ]