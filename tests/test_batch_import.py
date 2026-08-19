"""
Tests for batch import service.
"""

import unittest
import csv
import io
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

from src.services.batch_import_service import (
    BatchImportService, BatchImportResult, BatchImportError
)


class TestBatchImportError(unittest.TestCase):
    """Test BatchImportError class"""
    
    def test_batch_import_error_creation(self):
        """Test creating a BatchImportError"""
        errors = ["Invalid email", "Missing name"]
        error = BatchImportError(2, "test@example.com", errors)
        
        self.assertEqual(error.row_number, 2)
        self.assertEqual(error.email, "test@example.com")
        self.assertEqual(error.errors, errors)
    
    def test_batch_import_error_to_dict(self):
        """Test converting BatchImportError to dict"""
        error = BatchImportError(5, "user@example.com", ["Error 1", "Error 2"])
        result = error.to_dict()
        
        self.assertEqual(result['row'], 5)
        self.assertEqual(result['email'], "user@example.com")
        self.assertEqual(result['errors'], ["Error 1", "Error 2"])
    
    def test_batch_import_error_default_email(self):
        """Test BatchImportError with default email"""
        error = BatchImportError(3, errors=["Some error"])
        
        self.assertEqual(error.email, "unknown")


class TestBatchImportResult(unittest.TestCase):
    """Test BatchImportResult class"""
    
    def test_result_creation(self):
        """Test creating a BatchImportResult"""
        result = BatchImportResult()
        
        self.assertEqual(result.total_rows, 0)
        self.assertEqual(result.created_count, 0)
        self.assertEqual(result.updated_count, 0)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(len(result.errors), 0)
    
    def test_result_to_dict_success(self):
        """Test result dict with no errors"""
        result = BatchImportResult()
        result.total_rows = 3
        result.created_count = 2
        result.updated_count = 1
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict['status'], 'success')
        self.assertEqual(result_dict['summary']['total'], 3)
        self.assertEqual(result_dict['summary']['created'], 2)
        self.assertEqual(result_dict['summary']['updated'], 1)
        self.assertEqual(result_dict['summary']['errors'], 0)
    
    def test_result_to_dict_partial(self):
        """Test result dict with some errors"""
        result = BatchImportResult()
        result.total_rows = 3
        result.created_count = 2
        result.errors.append(BatchImportError(3, "bad@email", ["Invalid email"]))
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict['status'], 'partial')
        self.assertEqual(result_dict['summary']['errors'], 1)
    
    def test_result_to_dict_failed(self):
        """Test result dict with all errors"""
        result = BatchImportResult()
        result.total_rows = 2
        result.errors.append(BatchImportError(2, "bad@email", ["Invalid email"]))
        result.errors.append(BatchImportError(3, "bad2@email", ["Invalid format"]))
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict['status'], 'failed')


class TestBatchImportService(unittest.TestCase):
    """Test BatchImportService class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_session = Mock()
        self.mock_user_repo = Mock()
        self.mock_sub_repo = Mock()
        
        self.service = BatchImportService(self.mock_session)
        self.service.user_repo = self.mock_user_repo
        self.service.subscription_repo = self.mock_sub_repo
    
    def test_email_validation_valid(self):
        """Test valid email validation"""
        valid_emails = [
            "user@example.com",
            "john.doe@company.gov.co",
            "test+tag@domain.co.uk",
            "123@numbers.org"
        ]
        
        for email in valid_emails:
            self.assertTrue(
                BatchImportService._is_valid_email(email),
                f"Expected {email} to be valid"
            )
    
    def test_email_validation_invalid(self):
        """Test invalid email validation"""
        invalid_emails = [
            "notanemail",
            "@nodomain.com",
            "user@",
            "user @space.com",
            "user@domain",
            ""
        ]
        
        for email in invalid_emails:
            self.assertFalse(
                BatchImportService._is_valid_email(email),
                f"Expected {email} to be invalid"
            )
    
    def test_validate_headers_valid(self):
        """Test header validation with valid headers"""
        headers = ['Correo', 'Nombre', 'Departamento', 'reporte_gfw']
        result = self.service._validate_headers(headers)
        
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['errors']), 0)
    
    def test_validate_headers_missing_required(self):
        """Test header validation with missing required columns"""
        headers = ['Correo', 'Departamento']  # Missing 'Nombre'
        result = self.service._validate_headers(headers)
        
        self.assertFalse(result['valid'])
        self.assertIn("Missing required columns", result['errors'][0])
    
    def test_validate_headers_no_subscriptions(self):
        """Test header validation with no subscription columns"""
        headers = ['Correo', 'Nombre', 'Departamento']
        result = self.service._validate_headers(headers)
        
        self.assertFalse(result['valid'])
        self.assertIn("No subscription columns found", result['errors'][0])
    
    def test_validate_and_normalize_row_valid(self):
        """Test validating and normalizing a valid row"""
        row = {
            'Correo': 'USER@EXAMPLE.COM',
            'Nombre': '  John Doe  ',
            'Departamento': 'Engineering',
            'Municipio': '11001',
            'reporte_gfw': '1',
            'monthly_built_area': '0'
        }
        
        errors, normalized = self.service._validate_and_normalize_row(row, 2)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(normalized['email'], 'user@example.com')
        self.assertEqual(normalized['name'], 'John Doe')
        self.assertEqual(normalized['department'], 'Engineering')
        self.assertEqual(normalized['municipality_code'], '11001')
        self.assertEqual(normalized['subscriptions']['weekly_alerts'], True)
        self.assertEqual(normalized['subscriptions']['monthly_built_area'], False)
    
    def test_validate_and_normalize_row_missing_email(self):
        """Test validating a row with missing email"""
        row = {'Nombre': 'John Doe', 'reporte_gfw': '1'}
        
        errors, normalized = self.service._validate_and_normalize_row(row, 2)
        
        self.assertGreater(len(errors), 0)
        self.assertIn("Email", errors[0])
    
    def test_validate_and_normalize_row_invalid_email(self):
        """Test validating a row with invalid email"""
        row = {
            'Correo': 'not-an-email',
            'Nombre': 'John Doe',
            'reporte_gfw': '1'
        }
        
        errors, normalized = self.service._validate_and_normalize_row(row, 2)
        
        self.assertGreater(len(errors), 0)
        self.assertIn("Invalid email format", errors[0])
    
    def test_validate_and_normalize_row_invalid_subscription_value(self):
        """Test validating a row with invalid subscription value"""
        row = {
            'Correo': 'user@example.com',
            'Nombre': 'John Doe',
            'reporte_gfw': 'maybe'  # Invalid value
        }
        
        errors, normalized = self.service._validate_and_normalize_row(row, 2)
        
        self.assertGreater(len(errors), 0)
        self.assertIn("Invalid subscription value", errors[0])
    
    def test_generate_template_csv(self):
        """Test generating CSV template"""
        template = self.service.generate_template_csv()
        
        self.assertIn('Correo', template)
        self.assertIn('Nombre', template)
        self.assertIn('Departamento', template)
        self.assertIn('reporte_gfw', template)
        self.assertIn('monthly_built_area', template)
        self.assertIn('reporte_paramos', template)
        self.assertIn('emilio.rodriguez@example.gov.co', template)
        self.assertIn(';', template)  # Semicolon delimiter
    
    def test_import_empty_csv(self):
        """Test importing an empty CSV file"""
        csv_content = ""
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'test.csv'
        csv_file.filename = 'test.csv'
        
        result = self.service.import_users_batch(csv_file)
        
        self.assertFalse(result.created_count > 0 or result.updated_count > 0)
        self.assertGreater(len(result.errors), 0)
    
    def test_import_csv_with_valid_new_users(self):
        """Test importing CSV with new users"""
        # Setup mocks
        self.mock_user_repo.get_by_email.return_value = None
        new_user = Mock()
        new_user.id = uuid4()
        self.mock_user_repo.create.return_value = new_user
        self.mock_sub_repo.get_user_subscriptions.return_value = []
        
        # Create CSV content
        csv_content = "Correo;Nombre;Departamento;reporte_gfw;monthly_built_area\n"
        csv_content += "john@example.com;John Doe;Engineering;1;0\n"
        csv_content += "jane@example.com;Jane Smith;Design;0;1\n"
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'test.csv'
        csv_file.filename = 'test.csv'
        
        result = self.service.import_users_batch(csv_file)
        
        # Should have created 2 users
        self.assertEqual(result.created_count, 2)
        self.assertEqual(result.updated_count, 0)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(self.mock_user_repo.create.call_count, 2)
    
    def test_import_csv_with_existing_users(self):
        """Test importing CSV with existing users (upsert)"""
        # Setup mocks
        existing_user = Mock()
        existing_user.id = uuid4()
        self.mock_user_repo.get_by_email.return_value = existing_user
        self.mock_sub_repo.get_user_subscriptions.return_value = []
        
        csv_content = "Correo;Nombre;Departamento;reporte_gfw;monthly_built_area\n"
        csv_content += "john@example.com;John Doe;Engineering;1;0\n"
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'test.csv'
        csv_file.filename = 'test.csv'
        
        result = self.service.import_users_batch(csv_file)
        
        # Should have updated 1 user
        self.assertEqual(result.created_count, 0)
        self.assertEqual(result.updated_count, 1)
        self.assertEqual(len(result.errors), 0)
        self.mock_user_repo.update.assert_called_once()
    
    def test_import_csv_with_invalid_rows(self):
        """Test importing CSV with some invalid rows"""
        # Setup mocks
        self.mock_user_repo.get_by_email.return_value = None
        new_user = Mock()
        new_user.id = uuid4()
        self.mock_user_repo.create.return_value = new_user
        self.mock_sub_repo.get_user_subscriptions.return_value = []
        
        csv_content = "Correo;Nombre;reporte_gfw;monthly_built_area\n"
        csv_content += "john@example.com;John Doe;1;0\n"  # Valid
        csv_content += ";Jane Smith;0;1\n"  # Missing email
        csv_content += "invalid-email;Bob;1;1\n"  # Invalid email
        csv_content += "valid@example.com;Valid User;1;0\n"  # Valid
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'test.csv'
        csv_file.filename = 'test.csv'
        
        result = self.service.import_users_batch(csv_file)
        
        # Should have created 2 valid users
        self.assertEqual(result.created_count, 2)
        # Should have skipped 2 invalid rows
        self.assertEqual(result.skipped_count, 2)
        # Should have 2 errors
        self.assertEqual(len(result.errors), 2)


class TestBatchImportIntegration(unittest.TestCase):
    """Integration tests for batch import (would need real DB setup)"""
    
    def test_import_result_dict_structure(self):
        """Test that import result has correct structure"""
        result = BatchImportResult()
        result.total_rows = 5
        result.created_count = 3
        result.updated_count = 1
        result.skipped_count = 1
        result.errors.append(BatchImportError(5, "bad@email", ["Invalid format"]))
        
        result_dict = result.to_dict()
        
        # Verify structure
        self.assertIn('status', result_dict)
        self.assertIn('summary', result_dict)
        self.assertIn('errors', result_dict)
        
        self.assertIn('total', result_dict['summary'])
        self.assertIn('created', result_dict['summary'])
        self.assertIn('updated', result_dict['summary'])
        self.assertIn('skipped', result_dict['summary'])
        self.assertIn('errors', result_dict['summary'])
        
        self.assertIsInstance(result_dict['errors'], list)


if __name__ == '__main__':
    unittest.main()
