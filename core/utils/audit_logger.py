from django.db import transaction
from core.models import Log, LogDetail, Event
import uuid


class AuditLogger:
    """Manages audit logging consistently (text-based version)."""

    @staticmethod
    def get_user_agent(request):
        """Gets the browser's user agent."""
        return request.META.get('HTTP_USER_AGENT', '') if request else None

    @staticmethod
    def extract_user_info(user):
        """Extracts user info for logging."""
        if not user or not hasattr(user, "id"):
            return {
                "user_id": None,
                "user_name": "System",
                "user_email": None,
                "country_abbreviation": None,
                "identity_document_abbreviation": None,
                "document": None,
            }

        info = {
            "user_id": user.id,
            "user_name": getattr(user, "username", None),
            "user_email": getattr(user, "email", None),
            "country_abbreviation": None,
            "identity_document_abbreviation": None,
            "document": getattr(user, "document", None),
        }

        # Safe chain lookup (no FK joins, just attributes)
        try:
            if hasattr(user, "key_identity_document") and user.key_identity_document:
                doc = user.key_identity_document
                info["identity_document_abbreviation"] = getattr(doc, "abbreviation", None)
                if hasattr(doc, "key_country") and doc.key_country:
                    info["country_abbreviation"] = getattr(doc.key_country, "abbreviation", None)
        except Exception:
            pass

        return info

    @staticmethod
    @transaction.atomic
    def log_action(event_abbreviation, user, key_record, table_name, module_name, changes=None, request=None):
        """
        Register an action in the audit system using text-based logging.
        """
        try:
            # Get event info
            try:
                event = Event.objects.get(abbreviation=event_abbreviation)
                event_name = event.name_es
            except Event.DoesNotExist:
                return {
                    "is_error": True,
                    "message": f"Event '{event_abbreviation}' does not exist."
                }

            # Get user and environment info
            user_info = AuditLogger.extract_user_info(user)
            user_agent = AuditLogger.get_user_agent(request)

            # Create log (text-based)
            log = Log.objects.create(
                id=uuid.uuid4(),
                event_abbreviation=event_abbreviation,
                event_name=event_name,
                user_id=user_info["user_id"],
                user_name=user_info["user_name"],
                user_email=user_info["user_email"],
                country_abbreviation=user_info["country_abbreviation"],
                identity_document_abbreviation=user_info["identity_document_abbreviation"],
                document=user_info["document"],
                record_id=key_record,
                table_name=table_name,
                module_name=module_name,
                user_agent=user_agent
            )

            # Register field-level details (if any)
            if changes:
                for change in changes:
                    LogDetail.objects.create(
                        id=uuid.uuid4(),
                        key_log=log,
                        column_name=change.get("column_name", ""),
                        old_value=str(change.get("old_value", "")) or "",
                        new_value=str(change.get("new_value", "")) or ""
                    )

            return {
                "is_error": False,
                "message": "Log registered successfully",
                "log_id": log.id
            }

        except Exception as e:
            return {
                "is_error": True,
                "message": f"Error registering log: {str(e)}"
            }

    # ---------- CRUD / Specific Methods ----------

    @staticmethod
    def log_create(user, key_record, table_name, module_name, data, request=None):
        """Logs record creation."""
        changes = [
            {
                "column_name": key,
                "old_value": "",
                "new_value": value
            }
            for key, value in data.items()
            if value not in [None, '']
        ]
        return AuditLogger.log_action('CRT', user, key_record, table_name, module_name, changes, request)

    @staticmethod
    def log_update(user, key_record, table_name, module_name, changes, request=None):
        """Logs record updates."""
        real_changes = [
            change for change in changes
            if str(change.get('old_value', '')) != str(change.get('new_value', ''))
        ]

        if not real_changes:
            return {"is_error": False, "message": "No changes to register"}

        return AuditLogger.log_action('UPD', user, key_record, table_name, module_name, real_changes, request)

    @staticmethod
    def log_delete(user, key_record, table_name, module_name, old_data, request=None):
        """Logs record deletion."""
        changes = [
            {
                "column_name": key,
                "old_value": value,
                "new_value": ""
            }
            for key, value in old_data.items()
            if value not in [None, '']
        ]
        return AuditLogger.log_action('DEL', user, key_record, table_name, module_name, changes, request)