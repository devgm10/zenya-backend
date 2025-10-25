from django.test import TestCase
from django.db import connection
from django.db.utils import OperationalError

class DatabaseConnectionTest(TestCase):
    def test_database_connection(self):
        """✅ Test that verifies the PostgreSQL database connection works correctly"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()
                self.assertEqual(row[0], 1, "The database did not return the expected value.")
        except OperationalError as e:
            self.fail(f"Could not connect to the database: {e}")