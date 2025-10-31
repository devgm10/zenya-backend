import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Status(models.Model):
    """
    Represents the operational state of system entities.
    
    Common states include:
    - Active: Entity is operational and visible
    - Inactive: Entity is temporarily disabled
    - Deleted: Entity is soft-deleted (hidden but not removed)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_es = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_status'
        unique_together = [['name_es', 'name_en']]

    def __str__(self):
        return f"{self.abbreviation} - {self.name_en}"


class Country(models.Model):
    """
    Represents a sovereign nation or territory.
    
    Used for:
    - Associating identity documents with their issuing country
    - Geographic classification of users
    - International compliance and regulations
    
    Examples: Peru (PE), Argentina (AR), Colombia (CO)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_es = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=3, unique=True)
    iso_code = models.CharField(max_length=3, unique=True, null=True, blank=True)
    phone_code = models.CharField(max_length=5, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key_status = models.ForeignKey(
        Status, 
        on_delete=models.PROTECT,
        related_name='countries'
    )

    class Meta:
        db_table = 'core_country'
        verbose_name_plural = 'Countries'
        unique_together = [['name_es', 'name_en']]

    def __str__(self):
        return f"{self.abbreviation} - {self.name_en}"


class IdentityDocument(models.Model):
    """
    Defines valid types of identity documents recognized by the system.
    
    Each document type is associated with a country that issues it and may have
    specific validation rules (format, length, checksum algorithms).
    
    Examples:
    - DNI (Peru): National Identity Document, 8 digits
    - Passport (International): Alphanumeric, variable length
    - CE (Peru): Foreign Resident Card
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_es = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10, unique=True)
    regex_pattern = models.CharField(
        max_length=200, 
        null=True, 
        blank=True,
        help_text="Regular expression to validate document format"
    )
    min_length = models.IntegerField(default=1)
    max_length = models.IntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key_country = models.ForeignKey(
        Country, 
        on_delete=models.PROTECT,
        related_name='identity_documents'
    )
    key_status = models.ForeignKey(
        Status, 
        on_delete=models.PROTECT,
        related_name='identity_documents'
    )

    class Meta:
        db_table = 'core_identity_document'
        unique_together = [
            ['name_es', 'name_en'],
            ['abbreviation', 'key_country']
        ]

    def __str__(self):
        return f"{self.abbreviation} - {self.name_en} ({self.key_country.abbreviation})"


class User(AbstractUser):
    """
    Extended user model with additional authentication and identity verification.
    
    Inherits from Django's AbstractUser which provides:
    - username, password, email (authentication)
    - first_name, last_name (basic profile)
    - is_active, is_staff, is_superuser (permissions)
    - date_joined, last_login (audit)
    
    Additional fields:
    - Identity document information for KYC/verification
    - Failed login tracking for security
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.CharField(max_length=50)
    failed_login_attempts = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    key_identity_document = models.ForeignKey(
        IdentityDocument, 
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True
    )
    key_status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'document']

    class Meta:
        db_table = 'core_user'
        unique_together = [['key_identity_document', 'document']]

    def set_password(self, raw_password):
        """
        Override to reset security flags when password is changed.
        """
        # Resetear intentos fallidos y bloqueos
        self.failed_login_attempts = 0
        self.is_locked = False
        self.locked_until = None
        
        # Hashear el password
        super().set_password(raw_password)

    def __str__(self):
        return f"{self.username} ({self.document})"
    
    def get_full_document(self):
        """Returns formatted document with type. Example: DNI: 12345678"""
        return f"{self.key_identity_document.abbreviation}: {self.document}"