"""
Unit tests for database backup system
"""

import os
import tempfile
import subprocess
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import pytest
from datetime import datetime, timedelta

from app.backup_tasks import (
    create_database_backup,
    verify_backup,
    cleanup_old_backups,
    scheduled_backup_workflow
)


class TestBackupTasks:
    """Test backup Celery tasks"""
    
    @pytest.fixture
    def mock_vault_client(self):
        """Mock Vault client"""
        with patch('app.backup_tasks.get_vault_client') as mock:
            vault_client = MagicMock()
            vault_client.get_secret.return_value = {
                'access_key': 'test_access_key',
                'secret_key': 'test_secret_key',
                'bucket': 'test-bucket',
                'endpoint': 'test.endpoint.com'
            }
            mock.return_value = vault_client
            yield vault_client
    
    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess calls"""
        with patch('app.backup_tasks.subprocess.run') as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="Database backup created successfully (1000 bytes)\nBackup compressed successfully (500 bytes, 50% of original)\nuploaded successfully to s3://test-bucket/backup.sql.gz",
                stderr=""
            )
            yield mock
    
    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary backup directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / "backups"
            backup_dir.mkdir()
            yield backup_dir
    
    def test_create_database_backup_success(self, mock_vault_client, mock_subprocess):
        """Test successful database backup creation"""
        # Mock the task context
        with patch('app.backup_tasks.Path') as mock_path:
            script_path = MagicMock()
            script_path.exists.return_value = True
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            # Execute task
            result = create_database_backup.apply(args=[True])
            backup_info = result.get()
            
            # Verify result
            assert backup_info['status'] == 'success'
            assert backup_info['uploaded_to_s3'] is True
            assert 'duration_seconds' in backup_info
            assert 'compressed_size' in backup_info
            assert backup_info['compressed_size'] == 500
            assert 'original_size' in backup_info
            assert backup_info['original_size'] == 1000
            
            # Verify subprocess was called
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args
            assert str(script_path) in call_args[0][0]
    
    def test_create_database_backup_no_s3(self, mock_subprocess):
        """Test database backup without S3 upload"""
        with patch('app.backup_tasks.Path') as mock_path:
            script_path = MagicMock()
            script_path.exists.return_value = True
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            # Execute task without S3
            result = create_database_backup.apply(args=[False])
            backup_info = result.get()
            
            # Verify result
            assert backup_info['status'] == 'success'
            assert backup_info['uploaded_to_s3'] is False
    
    def test_create_database_backup_script_not_found(self):
        """Test backup failure when script is not found"""
        with patch('app.backup_tasks.Path') as mock_path:
            script_path = MagicMock()
            script_path.exists.return_value = False
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            # Execute task and expect failure
            with pytest.raises(FileNotFoundError):
                result = create_database_backup.apply(args=[True])
                result.get()
    
    def test_create_database_backup_script_failure(self, mock_vault_client):
        """Test backup failure when script fails"""
        with patch('app.backup_tasks.Path') as mock_path, \
             patch('app.backup_tasks.subprocess.run') as mock_subprocess:
            
            script_path = MagicMock()
            script_path.exists.return_value = True
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            # Mock script failure
            mock_subprocess.side_effect = subprocess.CalledProcessError(
                1, 'backup-script', stderr="Database connection failed"
            )
            
            # Execute task and expect failure
            with pytest.raises(Exception) as exc_info:
                result = create_database_backup.apply(args=[True])
                result.get()
            
            assert "Backup script failed" in str(exc_info.value)
    
    def test_verify_backup_success(self, mock_subprocess):
        """Test successful backup verification"""
        with patch('app.backup_tasks.Path') as mock_path:
            script_path = MagicMock()
            script_path.exists.return_value = True
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            # Mock verification output
            mock_subprocess.return_value.stdout = """
            Total verified: 3
            Passed: 3
            Failed: 0
            Success rate: 100.0%
            """
            
            # Execute task
            result = verify_backup.apply(args=[None, False])
            verify_info = result.get()
            
            # Verify result
            assert verify_info['status'] == 'success'
            assert verify_info['total_verified'] == 3
            assert verify_info['total_passed'] == 3
            assert verify_info['total_failed'] == 0
            assert verify_info['success_rate'] == '100.0%'
    
    def test_verify_backup_specific_file(self, mock_subprocess):
        """Test verification of specific backup file"""
        with patch('app.backup_tasks.Path') as mock_path:
            script_path = MagicMock()
            script_path.exists.return_value = True
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            backup_file = "/path/to/backup.sql.gz"
            
            # Execute task
            result = verify_backup.apply(args=[backup_file, False])
            verify_info = result.get()
            
            # Verify result
            assert verify_info['status'] == 'success'
            assert verify_info['backup_file'] == backup_file
            assert verify_info['verified_s3'] is False
            
            # Verify correct arguments were passed to script
            call_args = mock_subprocess.call_args[0][0]
            assert "--file" in call_args
            assert backup_file in call_args
    
    def test_cleanup_old_backups(self, temp_backup_dir):
        """Test cleanup of old backup files"""
        # Create test backup files
        old_backup = temp_backup_dir / "reddit_publisher_20240101_120000.sql.gz"
        recent_backup = temp_backup_dir / "reddit_publisher_20240201_120000.sql.gz"
        
        old_backup.touch()
        recent_backup.touch()
        
        # Set old file modification time
        old_time = (datetime.utcnow() - timedelta(days=35)).timestamp()
        os.utime(old_backup, (old_time, old_time))
        
        with patch('app.backup_tasks.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_backup_dir.parent
            mock_path.return_value.parent.parent.__truediv__.return_value = temp_backup_dir
            
            # Execute cleanup task
            result = cleanup_old_backups.apply(args=[30])
            cleanup_info = result.get()
            
            # Verify result
            assert cleanup_info['status'] == 'success'
            assert cleanup_info['retention_days'] == 30
            assert cleanup_info['local_deleted'] == 1
            
            # Verify old file was deleted, recent file remains
            assert not old_backup.exists()
            assert recent_backup.exists()
    
    def test_scheduled_backup_workflow(self, mock_vault_client, mock_subprocess):
        """Test complete scheduled backup workflow"""
        with patch('app.backup_tasks.Path') as mock_path, \
             patch('app.backup_tasks.create_database_backup') as mock_backup, \
             patch('app.backup_tasks.verify_backup') as mock_verify, \
             patch('app.backup_tasks.cleanup_old_backups') as mock_cleanup, \
             patch('time.sleep'):  # Skip sleep in test
            
            # Mock successful task results
            mock_backup.apply.return_value.get.return_value = {
                'status': 'success',
                'duration_seconds': 30.0,
                'compressed_size': 1000
            }
            
            mock_verify.apply.return_value.get.return_value = {
                'status': 'success',
                'total_verified': 2,
                'total_passed': 2,
                'total_failed': 0
            }
            
            mock_cleanup.apply.return_value.get.return_value = {
                'status': 'success',
                'local_deleted': 1,
                's3_deleted': 0
            }
            
            # Execute workflow
            result = scheduled_backup_workflow.apply()
            workflow_info = result.get()
            
            # Verify result
            assert workflow_info['status'] == 'success'
            assert len(workflow_info['steps_completed']) == 3
            assert 'backup_created' in workflow_info['steps_completed']
            assert 'backup_verified' in workflow_info['steps_completed']
            assert 'cleanup_completed' in workflow_info['steps_completed']
            
            # Verify all sub-tasks were called
            mock_backup.apply.assert_called_once_with(args=[True])
            mock_verify.apply.assert_called_once_with(args=[None, False])
            mock_cleanup.apply.assert_called_once_with(args=[30])
    
    def test_scheduled_backup_workflow_partial_failure(self, mock_vault_client):
        """Test workflow behavior when one step fails"""
        with patch('app.backup_tasks.create_database_backup') as mock_backup, \
             patch('app.backup_tasks.verify_backup') as mock_verify:
            
            # Mock backup success but verification failure
            mock_backup.apply.return_value.get.return_value = {
                'status': 'success',
                'duration_seconds': 30.0
            }
            
            mock_verify.apply.return_value.get.side_effect = Exception("Verification failed")
            
            # Execute workflow and expect failure
            with pytest.raises(Exception) as exc_info:
                result = scheduled_backup_workflow.apply()
                result.get()
            
            assert "Backup workflow failed" in str(exc_info.value)


class TestBackupScripts:
    """Test backup shell scripts"""
    
    def test_backup_script_exists(self):
        """Test that backup script exists and is executable"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "backup-database.sh"
        assert script_path.exists(), "Backup script not found"
        assert os.access(script_path, os.X_OK), "Backup script is not executable"
    
    def test_restore_script_exists(self):
        """Test that restore script exists and is executable"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "restore-database.sh"
        assert script_path.exists(), "Restore script not found"
        assert os.access(script_path, os.X_OK), "Restore script is not executable"
    
    def test_verify_script_exists(self):
        """Test that verification script exists and is executable"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "verify-backup.sh"
        assert script_path.exists(), "Verification script not found"
        assert os.access(script_path, os.X_OK), "Verification script is not executable"
    
    @pytest.mark.integration
    def test_backup_script_help(self):
        """Test backup script help output"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "backup-database.sh"
        
        # Test script can be executed (will fail due to missing DB, but should show help-like output)
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, 'POSTGRES_PASSWORD': 'test'}
        )
        
        # Script should fail but produce some output
        assert result.stderr or result.stdout
    
    @pytest.mark.integration
    def test_restore_script_help(self):
        """Test restore script help output"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "restore-database.sh"
        
        # Test help flag
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "--file" in result.stdout
        assert "--s3-key" in result.stdout
    
    @pytest.mark.integration
    def test_verify_script_help(self):
        """Test verification script help output"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "verify-backup.sh"
        
        # Test help flag
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "--all" in result.stdout
        assert "--file" in result.stdout


class TestVaultBackupTasks:
    """Test Vault backup Celery tasks"""
    
    @pytest.fixture
    def mock_vault_client(self):
        """Mock Vault client for Vault backup tests"""
        with patch('app.backup_tasks.get_vault_client') as mock:
            vault_client = MagicMock()
            vault_client.get_secret.return_value = {
                'access_key': 'test_access_key',
                'secret_key': 'test_secret_key',
                'bucket': 'test-bucket',
                'endpoint': 'test.endpoint.com'
            }
            mock.return_value = vault_client
            yield vault_client
    
    def test_create_vault_backup_success(self, mock_vault_client):
        """Test successful Vault backup creation"""
        with patch('app.backup_tasks.subprocess.run') as mock_subprocess, \
             patch('app.backup_tasks.Path') as mock_path:
            
            # Mock script path
            script_path = MagicMock()
            script_path.exists.return_value = True
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            # Mock successful script execution
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout="Vault backup created successfully (500 bytes)\nConfiguration backup created successfully (1000 bytes)\nsecrets backup completed: 5 backed up, 0 failed",
                stderr=""
            )
            
            # Import and execute task
            from app.backup_tasks import create_vault_backup
            result = create_vault_backup.apply(args=[True])
            backup_info = result.get()
            
            # Verify result
            assert backup_info['status'] == 'success'
            assert backup_info['uploaded_to_s3'] is True
            assert 'duration_seconds' in backup_info
            assert backup_info['vault_backup_size'] == 500
            assert backup_info['config_backup_size'] == 1000
            assert backup_info['secrets_backed_up'] == 5
            assert backup_info['secrets_failed'] == 0
    
    def test_restore_vault_secrets_success(self, mock_vault_client):
        """Test successful Vault secrets restore"""
        with patch('app.backup_tasks.subprocess.run') as mock_subprocess, \
             patch('app.backup_tasks.Path') as mock_path:
            
            # Mock script path
            script_path = MagicMock()
            script_path.exists.return_value = True
            mock_path.return_value.parent.parent = MagicMock()
            mock_path.return_value.parent.parent.__truediv__.return_value = script_path
            
            # Mock successful restore
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout="secrets restore completed: 5 restored, 0 failed",
                stderr=""
            )
            
            # Import and execute task
            from app.backup_tasks import restore_vault_secrets
            result = restore_vault_secrets.apply(args=["/path/to/vault_backup.json", None, False])
            restore_info = result.get()
            
            # Verify result
            assert restore_info['status'] == 'success'
            assert restore_info['vault_file'] == "/path/to/vault_backup.json"
            assert restore_info['test_mode'] is False
            assert restore_info['secrets_restored'] == 5
            assert restore_info['secrets_failed'] == 0
    
    def test_scheduled_vault_backup_workflow(self, mock_vault_client):
        """Test complete scheduled Vault backup workflow"""
        with patch('app.backup_tasks.create_vault_backup') as mock_backup:
            
            # Mock successful backup result
            mock_backup.apply.return_value.get.return_value = {
                'status': 'success',
                'duration_seconds': 45.0,
                'vault_backup_size': 500,
                'config_backup_size': 1000
            }
            
            # Import and execute workflow
            from app.backup_tasks import scheduled_vault_backup_workflow
            result = scheduled_vault_backup_workflow.apply()
            workflow_info = result.get()
            
            # Verify result
            assert workflow_info['status'] == 'success'
            assert 'vault_backup_created' in workflow_info['steps_completed']
            assert 'duration_seconds' in workflow_info
            
            # Verify backup task was called
            mock_backup.apply.assert_called_once_with(args=[True])


class TestVaultBackupScripts:
    """Test Vault backup shell scripts"""
    
    def test_vault_backup_script_exists(self):
        """Test that Vault backup script exists and is executable"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "backup-vault.sh"
        assert script_path.exists(), "Vault backup script not found"
        assert os.access(script_path, os.X_OK), "Vault backup script is not executable"
    
    def test_vault_restore_script_exists(self):
        """Test that Vault restore script exists and is executable"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "restore-vault.sh"
        assert script_path.exists(), "Vault restore script not found"
        assert os.access(script_path, os.X_OK), "Vault restore script is not executable"
    
    @pytest.mark.integration
    def test_vault_restore_script_help(self):
        """Test Vault restore script help output"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "restore-vault.sh"
        
        # Test help flag
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "--vault-file" in result.stdout
        assert "--s3-vault-key" in result.stdout


class TestDisasterRecoveryDocumentation:
    """Test disaster recovery documentation"""
    
    def test_disaster_recovery_doc_exists(self):
        """Test that disaster recovery documentation exists"""
        doc_path = Path(__file__).parent.parent.parent / "docs" / "disaster-recovery.md"
        assert doc_path.exists(), "Disaster recovery documentation not found"
        
        # Verify it has content
        content = doc_path.read_text()
        assert len(content) > 1000, "Disaster recovery documentation is too short"
        assert "Recovery Scenarios" in content
        assert "Database Corruption" in content
        assert "Vault Secrets Loss" in content


class TestBackupMetrics:
    """Test backup metrics integration"""
    
    def test_backup_metrics_import(self):
        """Test that backup metrics can be imported"""
        from app.monitoring.backup_metrics import backup_metrics
        
        assert backup_metrics is not None
        assert hasattr(backup_metrics, 'backup_duration')
        assert hasattr(backup_metrics, 'backup_size')
        assert hasattr(backup_metrics, 'backup_successes')
        assert hasattr(backup_metrics, 'backup_failures')
    
    def test_backup_metrics_tracking(self):
        """Test backup metrics tracking methods"""
        from app.monitoring.backup_metrics import backup_metrics
        
        # Test tracking methods exist and can be called
        backup_metrics.track_backup_success('database', 30.0, 1000)
        backup_metrics.track_backup_failure('database')
        backup_metrics.track_verification(15.0, 3, 0)
        backup_metrics.track_s3_upload('success', 10.0)
        
        # No assertions needed - just verify methods don't raise exceptions


if __name__ == "__main__":
    pytest.main([__file__])