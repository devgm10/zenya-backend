"""
Reusable audit system to log all CRUD operations.
Suggested location: core/utils/audit_logger.py
"""

from django.db import transaction
from core.models import Log, LogDetail, Event
import uuid


class AuditLogger:
    """Manages audit logging consistently."""
    
    @staticmethod
    def get_user_agent(request):
        """Gets the browser's user agent"""
        return request.META.get('HTTP_USER_AGENT', '') if request else None
    
    @staticmethod
    @transaction.atomic
    def log_action(event_abbreviation, user, key_record, table_name, module_name, changes=None, request=None):
        """
        Register an action in the audit system.
        
        Args:
            event_abbreviation (str): Event code (CRT, UPD, DEL, etc.)
            user: User who performed the action (can be None for system actions)
            key_record (UUID): ID of the affected record
            table_name (str): Name of the table (ex: 'core_status', 'core_country')
            module_name (str): Module name (ex: 'STATUS', 'COUNTRY')
            changes (list): List of dictionaries with the changes:
                [
                    {
                        "column": "name_es",
                        "old_value": "old value",
                        "new_value": "new value"
                    }
                ]
            request: Django request object (optional)
        
        Returns:
            dict: {"is_error": bool, "message": str, "log_id": UUID}
        """
        try:
            # Get event
            try:
                event = Event.objects.get(abbreviation=event_abbreviation)
            except Event.DoesNotExist:
                return {
                    "is_error": True,
                    "message": f"Event '{event_abbreviation}' does not exist. Must be created first."
                }
            
            # Get user agent if the request exists
            user_agent = AuditLogger.get_user_agent(request)
            
            # Create main log record
            log = Log.objects.create(
                id=uuid.uuid4(),
                key_event=event,
                key_user=user,
                key_record=key_record,
                table_name=table_name,
                module_name=module_name,
                user_agent=user_agent
            )
            
            # Create the details if there are changes
            if changes:
                for change in changes:
                    LogDetail.objects.create(
                        id=uuid.uuid4(),
                        key_log=log,
                        column_name=change.get('column_name', ''),
                        old_value=str(change.get('old_value', '')) if change.get('old_value') not in [None, ''] else '',
                        new_value=str(change.get('new_value', '')) if change.get('new_value') not in [None, ''] else ''
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
    
    @staticmethod
    def log_create(user, key_record, table_name, module_name, data, request=None):
        """
        Records the creation of a new record.
        
        Args:
            user: User who created the record
            key_record: ID of the new record
            table_name: Table name
            module_name: Module name
            data: Dictionary with the created data
            request: Django Request
        
        Returns:
            dict: {"is_error": bool, "message": str, "log_id": UUID}
        """
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
        """
        Records the update of a record.
        
        Args:
            user: User who updated the record
            key_record: ID of the updated record
            table_name: Table name
            module_name: Module name
            changes: List of changes with old_value and new_value
            request: Django Request
        
        Returns:
            dict: {"is_error": bool, "message": str, "log_id": UUID}
        """
        # Filter only the fields that actually changed
        real_changes = [
            change for change in changes 
            if str(change.get('old_value', '')) != str(change.get('new_value', ''))
        ]

        if not real_changes:
            return {
                "is_error": False,
                "message": "No changes to register"
            }
        
        return AuditLogger.log_action('UPD', user, key_record, table_name, module_name, real_changes, request)
    
    @staticmethod
    def log_delete(user, key_record, table_name, module_name, old_data, request=None):
        """
        Records the deletion of a record.
        
        Args:
            user: User who deleted the record
            key_record: ID of the deleted record
            table_name: Table name
            module_name: Module name
            old_data: Dictionary with the data that the record had before deletion
            request: Django Request
        
        Returns:
            dict: {"is_error": bool, "message": str, "log_id": UUID}
        """
        changes = [
            {
                "column": key,
                "old_value": value,
                "new_value": ""
            }
            for key, value in old_data.items()
            if value not in [None, '']
        ]
        return AuditLogger.log_action('DEL', user, key_record, table_name, module_name, changes, request)