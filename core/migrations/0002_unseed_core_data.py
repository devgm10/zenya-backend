from django.db import migrations
import uuid

def seed_core_data(apps, schema_editor):
    Status = apps.get_model('core', 'Status')
    Event = apps.get_model('core', 'Event')
    Country = apps.get_model('core', 'Country')
    IdentityDocument = apps.get_model('core', 'IdentityDocument')

    # Crear Status base
    statuses = [
        {"id": uuid.uuid4(), "name_es": "Activo", "name_en": "Active", "abbreviation": "ACT"},
        {"id": uuid.uuid4(), "name_es": "Inactivo", "name_en": "Inactive", "abbreviation": "INA"},
        {"id": uuid.uuid4(), "name_es": "Eliminado", "name_en": "Deleted", "abbreviation": "DEL"},
    ]
    created_statuses = {}
    for s in statuses:
        obj, created = Status.objects.get_or_create(
            abbreviation=s["abbreviation"],
            defaults=s
        )
        created_statuses[s["abbreviation"]] = obj

    # Crear Events base
    events = [
        {"id": uuid.uuid4(), "name_es": "Creación", "name_en": "Create", "abbreviation": "CRT"},
        {"id": uuid.uuid4(), "name_es": "Actualización", "name_en": "Update", "abbreviation": "UPD"},
        {"id": uuid.uuid4(), "name_es": "Eliminación", "name_en": "Delete", "abbreviation": "DEL"},
    ]
    for e in events:
        Event.objects.get_or_create(
            abbreviation=e["abbreviation"],
            defaults=e
        )

    # 3 Crear Countries base
    countries = [
        {"id": uuid.uuid4(), "name_es": "Perú", "name_en": "Peru", "abbreviation": "PE", "iso_code": "PE", "phone_code": "51"},
        {"id": uuid.uuid4(), "name_es": "México", "name_en": "Mexico", "abbreviation": "MX", "iso_code": "MX", "phone_code": "52"},
        {"id": uuid.uuid4(), "name_es": "Chile", "name_en": "Chile", "abbreviation": "CL", "iso_code": "CL", "phone_code": "56"},
    ]
    created_countries = {}
    for c in countries:
        obj, created = Country.objects.get_or_create(
            abbreviation=c["abbreviation"],
            defaults={**c, "key_status": created_statuses["ACT"]}
        )
        created_countries[c["abbreviation"]] = obj

    # 4 Crear IdentityDocuments base
    identity_docs = [
        # Perú
        {"abbreviation": "DNI", "name_es": "DNI", "name_en": "National ID", "key_country": created_countries["PE"]},
        {"abbreviation": "CE", "name_es": "Carné de Extranjería", "name_en": "Foreigner ID", "key_country": created_countries["PE"]},
        # México
        {"abbreviation": "CURP", "name_es": "CURP", "name_en": "Unique Population Registry Code", "key_country": created_countries["MX"]},
        {"abbreviation": "IFE", "name_es": "IFE", "name_en": "Voter ID", "key_country": created_countries["MX"]},
        # Chile
        {"abbreviation": "RUT", "name_es": "RUT", "name_en": "Rol Único Tributario", "key_country": created_countries["CL"]},
    ]
    for doc in identity_docs:
        IdentityDocument.objects.get_or_create(
            abbreviation=doc["abbreviation"],
            key_country=doc["key_country"],
            defaults={**doc, "key_status": created_statuses["ACT"], "min_length": 1, "max_length": 50}
        )


def unseed_core_data(apps, schema_editor):
    Status = apps.get_model('core', 'Status')
    Event = apps.get_model('core', 'Event')
    Country = apps.get_model('core', 'Country')
    IdentityDocument = apps.get_model('core', 'IdentityDocument')

    IdentityDocument.objects.filter(abbreviation__in=["DNI", "CE", "CURP", "IFE", "RUT"]).delete()
    Country.objects.filter(abbreviation__in=["PE", "MX", "CL"]).delete()
    Event.objects.filter(abbreviation__in=["CRT", "UPD", "DEL"]).delete()
    Status.objects.filter(abbreviation__in=["ACT", "INA", "DEL"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_core_data, unseed_core_data),
    ]