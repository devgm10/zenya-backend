"""
Generic CRUD class that can be reused for all models.
Location: core/views/generic_crud.py
"""

from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.db import transaction, models
from django.db.models import Q
from core.utils.audit_logger import AuditLogger
import uuid


class GenericCrud:
    """
    Generic CRUD operations that can be used with any model.
    
    Usage example:
        status_crud = GenericCrud(
            model=Status,
            serializer_class=StatusSerializer,
            table_name='core_status',
            module_name='STATUS',
            unique_fields=['name_es', 'name_en', 'abbreviation']
        )
    """

    def __init__(self, model, serializer_class, table_name, module_name, unique_fields=None):
        self.model = model
        self.serializer_class = serializer_class
        self.table_name = table_name
        self.module_name = module_name
        self.unique_fields = unique_fields or []

    def _response(self, is_error, message, data=None, status_code=status.HTTP_200_OK):
        """Unified response format."""
        return Response({
            "is_error": is_error,
            "message": message,
            "data": data
        }, status=status_code)

    def _validate_unique_constraints(self, data, instance=None):
        """
        Validates automatically all unique and UniqueConstraint fields.
        """
        # 1. Validate fields with unique=True
        for field in self.model._meta.get_fields():
            if getattr(field, 'unique', False):
                field_name = field.name
                value = data.get(field_name)
                if value is not None:
                    qs = self.model.objects.filter(**{field_name: value})
                    if instance:
                        qs = qs.exclude(pk=instance.pk)
                    if qs.exists():
                        raise ValidationError({field_name: f"'{value}' is already in use."})

        # 2. Validate UniqueConstraint combinations
        for constraint in self.model._meta.constraints:
            if isinstance(constraint, models.UniqueConstraint):
                field_names = constraint.fields
                filter_kwargs = {}
                skip = False
                for name in field_names:
                    if name not in data:
                        skip = True
                        break
                    filter_kwargs[name] = data[name]

                if skip:
                    continue

                qs = self.model.objects.filter(**filter_kwargs)
                if instance:
                    qs = qs.exclude(pk=instance.pk)
                if qs.exists():
                    fields_str = " + ".join(field_names)
                    raise ValidationError({
                        fields_str: f"A record with this combination already exists: {filter_kwargs}"
                    })

    def _validate_custom_unique_fields(self, data, instance=None):
        """
        Validates manually defined unique_fields list (custom).
        """
        if not self.unique_fields:
            return

        q_objects = Q()
        for field in self.unique_fields:
            if field in data:
                q_objects |= Q(**{field: data[field]})

        if not q_objects:
            return

        qs = self.model.objects.filter(q_objects)
        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise ValidationError("A record with these values already exists")

    def create(self, request):
        """Create a new record with audit logging."""
        try:
            # 1. Validate with serializer
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                return self._response(
                    True,
                    "Invalid data",
                    serializer.errors,
                    status.HTTP_400_BAD_REQUEST
                )

            data = serializer.validated_data

            # 2. Validate unique fields & constraints
            try:
                self._validate_unique_constraints(data)
                self._validate_custom_unique_fields(data)
            except ValidationError as ve:
                return self._response(
                    True,
                    "Duplicate record",
                    ve.detail if hasattr(ve, "detail") else ve.args,
                    status.HTTP_409_CONFLICT
                )

            # 3. Create record with audit
            with transaction.atomic():
                obj = serializer.save(id=uuid.uuid4())

                log_result = AuditLogger.log_create(
                    user=request.user,
                    key_record=obj.id,
                    table_name=self.table_name,
                    module_name=self.module_name,
                    data=data,
                    request=request
                )

                if log_result.get('is_error'):
                    transaction.set_rollback(True)
                    return self._response(
                        True,
                        f"Error registering audit: {log_result['message']}",
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                return self._response(
                    False,
                    f"{self.module_name} created successfully",
                    self.serializer_class(obj).data,
                    status.HTTP_201_CREATED
                )

        except Exception as error:
            return self._response(
                True,
                f"Error creating {self.module_name}: {str(error)}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request):
        """Updates an existing record with uniqueness validation and auditing."""
        try:
            record_id = request.data.get("id")
            if not record_id:
                return self._response(
                    True,
                    "Missing ID in request body",
                    status.HTTP_400_BAD_REQUEST
                )

            instance = self.model.objects.filter(pk=record_id).first()
            if not instance:
                return self._response(
                    True,
                    f"{self.module_name} not found",
                    status.HTTP_404_NOT_FOUND
                )

            serializer = self.serializer_class(instance, data=request.data, partial=True)
            if not serializer.is_valid():
                return self._response(
                    True,
                    "Invalid data",
                    serializer.errors,
                    status.HTTP_400_BAD_REQUEST
                )

            data = serializer.validated_data

            # Validar unicidad
            try:
                self._validate_unique_constraints(data, instance)
                self._validate_custom_unique_fields(data, instance)
            except ValidationError as ve:
                return self._response(
                    True,
                    "Uniqueness conflict",
                    ve.detail if hasattr(ve, "detail") else ve.args,
                    status.HTTP_409_CONFLICT
                )

            with transaction.atomic():
                # Guardar cambios y auditar
                old_data = self.serializer_class(instance).data
                obj = serializer.save()
                new_data = self.serializer_class(obj).data

                ignore_fields = {"created_at", "updated_at"}
                changes = []
                for field, old_value in old_data.items():
                    if field in ignore_fields:
                        continue
                    new_value = new_data.get(field)
                    if str(old_value) != str(new_value):
                        changes.append({
                            "column_name": field,
                            "old_value": old_value,
                            "new_value": new_value
                        })

                if changes:
                    log_result = AuditLogger.log_update(
                        user=request.user,
                        key_record=obj.id,
                        table_name=self.table_name,
                        module_name=self.module_name,
                        changes=changes,
                        request=request
                    )

                    if log_result.get("is_error"):
                        transaction.set_rollback(True)
                        return self._response(
                            True,
                            f"Error registering audit: {log_result['message']}",
                            status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                return self._response(
                    False,
                    f"{self.module_name} successfully updated",
                    self.serializer_class(obj).data,
                    status.HTTP_200_OK
                )

        except Exception as error:
            return self._response(
                True,
                f"Error updating {self.module_name}: {str(error)}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )