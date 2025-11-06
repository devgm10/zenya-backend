"""
Generic CRUD class that can be reused for all models.
Location: core/utils/generic_crud.py
"""

from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.db import transaction, models
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from core.utils.audit_logger import AuditLogger
import uuid


class GenericCrud:
    """
    Generic CRUD operations that can be used with any model.

    Usage example:
        country_crud = GenericCrud(
            model=Country,
            serializer_class=CountrySerializer,
            table_name='core_country',
            module_name='COUNTRY',
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

    # uniqueness validations (kept as you had)
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

    # CREATE
    def create(self, request):
        """Create a new record with audit logging."""
        try:
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                return self._response(
                    True,
                    "Invalid data",
                    serializer.errors,
                    status.HTTP_400_BAD_REQUEST
                )

            data = serializer.validated_data

            # Validate uniqueness
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

    # UPDATE
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

            # Uniqueness validation
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

    # GET / LIST
    def get(self, request, pk=None):
        """
        Retrieve a single record (pk provided) or list (no pk).
        - For list: supports ?include_deleted=true to show soft-deleted records.
        """
        try:
            # Single record
            if pk:
                instance = self.model.objects.filter(pk=pk).first()
                if not instance:
                    return self._response(True, f"{self.module_name} not found", status.HTTP_404_NOT_FOUND)
                return self._response(False, "Record found", self.serializer_class(instance).data)

            # List
            include_deleted = request.query_params.get('include_deleted', 'false').lower() == 'true'

            qs = self.model.objects.all()

            # If model uses key_status (soft delete style), exclude typical deleted abbreviations
            if hasattr(self.model, "key_status") and not include_deleted:
                qs = qs.exclude(
                    Q(key_status__abbreviation__iexact='DEL') |
                    Q(key_status__abbreviation__iexact='DELETED') |
                    Q(key_status__abbreviation__iexact='INACTIVE')
                )

            serializer = self.serializer_class(qs, many=True)
            return self._response(False, "Records listed successfully", serializer.data)

        except Exception as error:
            return self._response(
                True,
                f"Error fetching {self.module_name}: {str(error)}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # DELETE (soft / hard)
    def delete(self, request):
        """Deletes a record, supporting both soft and hard deletion with audit logging."""
        try:
            record_id = request.data.get("id")
            force_delete = bool(request.data.get("force", False))  # if true -> attempt hard delete

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

            # Model-level flags
            allow_soft = getattr(self.model, "allow_soft_delete", False)
            allow_hard = getattr(self.model, "allow_hard_delete", False)

            if not allow_soft and not allow_hard:
                return self._response(
                    True,
                    f"Deletion is not allowed for {self.module_name}.",
                    status.HTTP_403_FORBIDDEN
                )

            with transaction.atomic():
                delete_mode = None
                deleted_data = self.serializer_class(instance).data

                # Soft delete preferred if allowed and not forced
                if allow_soft and not force_delete:
                    # Require key_status on the model
                    if not hasattr(instance, "key_status"):
                        return self._response(
                            True,
                            f"{self.module_name} does not support soft deletion (missing key_status).",
                            status.HTTP_400_BAD_REQUEST
                        )

                    # Set to INACTIVE (must exist in Status)
                    from core.models import Status
                    inactive_status = Status.objects.filter(abbreviation__iexact="INACTIVE").first()
                    if not inactive_status:
                        return self._response(
                            True,
                            "Inactive status not found in Status table.",
                            status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    instance.key_status = inactive_status
                    instance.save(update_fields=["key_status", "updated_at"] if hasattr(instance, "updated_at") else ["key_status"])
                    delete_mode = "soft"

                # Hard delete if allowed and forced
                elif allow_hard and force_delete:
                    try:
                        instance.delete()
                        delete_mode = "hard"
                    except ProtectedError:
                        transaction.set_rollback(True)
                        return self._response(
                            True,
                            f"{self.module_name} cannot be physically deleted because it is referenced in another module.",
                            status.HTTP_409_CONFLICT
                        )

                else:
                    # Cases like allow_soft=False but allow_hard=True and not forced
                    if allow_hard and not force_delete:
                        return self._response(
                            True,
                            "Hard delete requires 'force' flag set to true.",
                            status.HTTP_400_BAD_REQUEST
                        )

                    return self._response(
                        True,
                        f"Invalid delete mode for {self.module_name}.",
                        status.HTTP_400_BAD_REQUEST
                    )

                # Audit the deletion
                log_result = AuditLogger.log_delete(
                    user=request.user,
                    key_record=record_id,
                    table_name=self.table_name,
                    module_name=self.module_name,
                    old_data=deleted_data,
                    request=request
                )

                if log_result.get("is_error"):
                    transaction.set_rollback(True)
                    return self._response(
                        True,
                        f"Error registering audit: {log_result['message']}",
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                message = (
                    f"{self.module_name} logically deleted (status set to INACTIVE)"
                    if delete_mode == "soft"
                    else f"{self.module_name} physically deleted"
                )

                return self._response(False, message, status_code=status.HTTP_200_OK)

        except Exception as error:
            return self._response(
                True,
                f"Error deleting {self.module_name}: {str(error)}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )