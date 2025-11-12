import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Status(models.Model):
    """Operational state of system entities."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_es = models.CharField(max_length=100, unique=True)
    name_en = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_status'


class Event(models.Model):
    """System event catalog for auditing."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_es = models.CharField(max_length=100, unique=True)
    name_en = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=3, unique=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_event'


class Country(models.Model):
    """Represents a sovereign nation or territory."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_es = models.CharField(max_length=100, unique=True)
    name_en = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=3, unique=True)
    iso_code = models.CharField(max_length=3, unique=True, null=True, blank=True)
    phone_code = models.CharField(max_length=5, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key_status = models.ForeignKey('Status', on_delete=models.PROTECT, related_name='countries')

    class Meta:
        db_table = 'core_country'


class IdentityDocument(models.Model):
    """Defines valid types of identity documents recognized by the system."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_es = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10, unique=True)
    regex_pattern = models.CharField(max_length=200, null=True, blank=True)
    min_length = models.IntegerField(default=1)
    max_length = models.IntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key_country = models.ForeignKey('Country', on_delete=models.PROTECT, related_name='identity_documents')
    key_status = models.ForeignKey('Status', on_delete=models.PROTECT, related_name='identity_documents')

    class Meta:
        db_table = 'core_identity_document'
        constraints = [
            models.UniqueConstraint(fields=['abbreviation', 'key_country'], name='uq_identity_country')
        ]


class User(AbstractUser):
    """Extended user model with identity verification."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.CharField(max_length=50)
    failed_login_attempts = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key_identity_document = models.ForeignKey('IdentityDocument', on_delete=models.PROTECT, related_name='users', null=True, blank=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'document']

    class Meta:
        db_table = 'core_user'
        constraints = [
            models.UniqueConstraint(fields=['key_identity_document', 'document'], name='uq_user_document_type')
        ]

    def set_password(self, raw_password):
        """Reset security flags when password is changed."""
        self.failed_login_attempts = 0
        self.is_locked = False
        self.locked_until = None
        super().set_password(raw_password)


class Log(models.Model):
    """Main audit log storing user and action metadata as immutable text."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_abbreviation = models.CharField(max_length=10)
    event_name = models.CharField(max_length=100)
    user_id = models.UUIDField(null=True, blank=True)
    user_name = models.CharField(max_length=150, null=True, blank=True)
    user_email = models.CharField(max_length=150, null=True, blank=True)
    country_abbreviation = models.CharField(max_length=5, null=True, blank=True)
    identity_document_abbreviation = models.CharField(max_length=10, null=True, blank=True)
    document = models.CharField(max_length=50, null=True, blank=True)
    record_id = models.UUIDField(null=True, blank=True)
    table_name = models.CharField(max_length=100)
    module_name = models.CharField(max_length=100)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_log'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['table_name']),
            models.Index(fields=['record_id']),
            models.Index(fields=['event_abbreviation']),
        ]


class LogDetail(models.Model):
    """Detailed field-level audit of changes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key_log = models.ForeignKey('Log', on_delete=models.CASCADE, related_name='details')
    column_name = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'core_log_detail'
        ordering = ['column_name']