"""
Database backup tasks for Reddit Ghost Publisher
Automated backup scheduling and management using Celery
"""

import os
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from celery import Task
from celery.exceptions import Retry

from app.celery_app import celery_app
from app.config import settings
# backup_metrics removed - using general metrics collection
from app.monitoring.logging import get_logger

logger = get_logger(__name__)


class BackupTask(Task):
    """Base class for backup tasks with error handling and metrics"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(
            "Backup task failed",
            task_id=task_id,
            exception=str(exc),
            args=args,
            kwargs=kwargs
        )
        backup_metrics.backup_failures.inc()
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(
            "Backup task completed successfully",
            task_id=task_id,
            result=retval
        )
        backup_metrics.backup_successes.inc()


@celery_app.task(
    bind=True,
    base=BackupTask,
    name="backup.create_database_backup",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    autoretry_for=(subprocess.CalledProcessError, OSError)
)
def create_database_backup(self, upload_to_s3: bool = True) -> Dict[str, Any]:
    """
    Create a database backup using the backup script
    
    Args:
        upload_to_s3: Whether to upload backup to S3
        
    Returns:
        Dict containing backup information
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting automated database backup", upload_to_s3=upload_to_s3)
        
        # Prepare environment variables for backup script
        env = os.environ.copy()
        env.update({
            'POSTGRES_HOST': settings.database_url.split('@')[1].split(':')[0] if '@' in settings.database_url else 'localhost',
            'POSTGRES_PORT': str(settings.database_url.split(':')[-1].split('/')[0]) if ':' in settings.database_url else '5432',
            'POSTGRES_DB': settings.database_url.split('/')[-1] if '/' in settings.database_url else 'reddit_publisher',
            'POSTGRES_USER': settings.database_url.split('://')[1].split(':')[0] if '://' in settings.database_url else 'postgres',
            'POSTGRES_PASSWORD': settings.database_url.split(':')[2].split('@')[0] if '@' in settings.database_url else 'postgres',
            'BACKUP_RETENTION_DAYS': '30',
        })
        
        # Add S3 configuration if available
        if upload_to_s3:
            try:
                from app.vault_client import get_vault_client
                vault_client = get_vault_client()
                s3_secrets = vault_client.get_secret('s3')
                
                env.update({
                    'S3_ACCESS_KEY': s3_secrets.get('access_key', ''),
                    'S3_SECRET_KEY': s3_secrets.get('secret_key', ''),
                    'S3_BUCKET': s3_secrets.get('bucket', 'reddit-publisher-backups'),
                    'S3_ENDPOINT': s3_secrets.get('endpoint', 'sgp1.digitaloceanspaces.com'),
                })
            except Exception as e:
                logger.warning("Failed to get S3 credentials from Vault", error=str(e))
                upload_to_s3 = False
        
        # Get script path
        script_path = Path(__file__).parent.parent / "scripts" / "backup-database.sh"
        
        if not script_path.exists():
            raise FileNotFoundError(f"Backup script not found: {script_path}")
        
        # Execute backup script
        logger.info("Executing backup script", script_path=str(script_path))
        
        result = subprocess.run(
            [str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
            check=True
        )
        
        # Parse backup information from script output
        backup_info = {
            'timestamp': start_time.isoformat(),
            'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
            'uploaded_to_s3': upload_to_s3,
            'script_output': result.stdout,
            'status': 'success'
        }
        
        # Extract backup file information from output
        for line in result.stdout.split('\n'):
            if 'Backup compressed successfully' in line:
                # Extract size information
                if 'bytes' in line:
                    size_part = line.split('(')[1].split(' bytes')[0]
                    backup_info['compressed_size'] = int(size_part)
            elif 'Database backup created successfully' in line:
                if 'bytes' in line:
                    size_part = line.split('(')[1].split(' bytes')[0]
                    backup_info['original_size'] = int(size_part)
            elif 'uploaded successfully to s3://' in line:
                s3_path = line.split('s3://')[1].strip()
                backup_info['s3_path'] = s3_path
        
        # Record metrics
        backup_metrics.backup_duration.observe(backup_info['duration_seconds'])
        if 'compressed_size' in backup_info:
            backup_metrics.backup_size.set(backup_info['compressed_size'])
        
        logger.info(
            "Database backup completed successfully",
            duration=backup_info['duration_seconds'],
            uploaded_to_s3=upload_to_s3,
            compressed_size=backup_info.get('compressed_size'),
            s3_path=backup_info.get('s3_path')
        )
        
        return backup_info
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Backup script failed with exit code {e.returncode}: {e.stderr}"
        logger.error("Backup script execution failed", error=error_msg, stderr=e.stderr)
        
        # Retry on script failures
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying backup task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=self.default_retry_delay * (2 ** self.request.retries))
        
        raise Exception(error_msg)
        
    except subprocess.TimeoutExpired:
        error_msg = "Backup script timed out after 1 hour"
        logger.error("Backup script timeout", error=error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Backup task failed: {str(e)}"
        logger.error("Backup task error", error=error_msg, exception_type=type(e).__name__)
        raise


@celery_app.task(
    bind=True,
    base=BackupTask,
    name="backup.verify_backup",
    max_retries=2,
    default_retry_delay=60
)
def verify_backup(self, backup_file: Optional[str] = None, verify_s3: bool = False) -> Dict[str, Any]:
    """
    Verify backup integrity using the verification script
    
    Args:
        backup_file: Specific backup file to verify (optional)
        verify_s3: Whether to verify S3 backups
        
    Returns:
        Dict containing verification results
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting backup verification", backup_file=backup_file, verify_s3=verify_s3)
        
        # Prepare environment variables
        env = os.environ.copy()
        
        if verify_s3:
            try:
                from app.vault_client import get_vault_client
                vault_client = get_vault_client()
                s3_secrets = vault_client.get_secret('s3')
                
                env.update({
                    'S3_ACCESS_KEY': s3_secrets.get('access_key', ''),
                    'S3_SECRET_KEY': s3_secrets.get('secret_key', ''),
                    'S3_BUCKET': s3_secrets.get('bucket', 'reddit-publisher-backups'),
                    'S3_ENDPOINT': s3_secrets.get('endpoint', 'sgp1.digitaloceanspaces.com'),
                })
            except Exception as e:
                logger.warning("Failed to get S3 credentials for verification", error=str(e))
                verify_s3 = False
        
        # Get script path
        script_path = Path(__file__).parent.parent / "scripts" / "verify-backup.sh"
        
        if not script_path.exists():
            raise FileNotFoundError(f"Verification script not found: {script_path}")
        
        # Build command arguments
        cmd_args = [str(script_path), "--report"]
        
        if backup_file:
            cmd_args.extend(["--file", backup_file])
        else:
            cmd_args.append("--all")
        
        if verify_s3:
            cmd_args.append("--s3")
        
        # Execute verification script
        logger.info("Executing verification script", script_path=str(script_path), args=cmd_args)
        
        result = subprocess.run(
            cmd_args,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes timeout
            check=True
        )
        
        # Parse verification results
        verification_info = {
            'timestamp': start_time.isoformat(),
            'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
            'backup_file': backup_file,
            'verified_s3': verify_s3,
            'script_output': result.stdout,
            'status': 'success'
        }
        
        # Extract verification statistics from output
        for line in result.stdout.split('\n'):
            if 'Total verified:' in line:
                verification_info['total_verified'] = int(line.split(':')[1].strip())
            elif 'Passed:' in line:
                verification_info['total_passed'] = int(line.split(':')[1].strip())
            elif 'Failed:' in line:
                verification_info['total_failed'] = int(line.split(':')[1].strip())
            elif 'Success rate:' in line:
                verification_info['success_rate'] = line.split(':')[1].strip()
        
        # Record metrics
        backup_metrics.verification_duration.observe(verification_info['duration_seconds'])
        if 'total_verified' in verification_info:
            backup_metrics.backups_verified.set(verification_info['total_verified'])
        if 'total_failed' in verification_info:
            backup_metrics.verification_failures.set(verification_info['total_failed'])
        
        logger.info(
            "Backup verification completed successfully",
            duration=verification_info['duration_seconds'],
            total_verified=verification_info.get('total_verified'),
            total_passed=verification_info.get('total_passed'),
            total_failed=verification_info.get('total_failed')
        )
        
        return verification_info
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Verification script failed with exit code {e.returncode}: {e.stderr}"
        logger.error("Verification script execution failed", error=error_msg, stderr=e.stderr)
        
        # Don't retry on verification failures - they indicate real issues
        raise Exception(error_msg)
        
    except subprocess.TimeoutExpired:
        error_msg = "Verification script timed out after 30 minutes"
        logger.error("Verification script timeout", error=error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Verification task failed: {str(e)}"
        logger.error("Verification task error", error=error_msg, exception_type=type(e).__name__)
        raise


@celery_app.task(
    bind=True,
    base=BackupTask,
    name="backup.cleanup_old_backups",
    max_retries=2,
    default_retry_delay=60
)
def cleanup_old_backups(self, retention_days: int = 30) -> Dict[str, Any]:
    """
    Clean up old backup files locally and in S3
    
    Args:
        retention_days: Number of days to retain backups
        
    Returns:
        Dict containing cleanup results
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting backup cleanup", retention_days=retention_days)
        
        cleanup_info = {
            'timestamp': start_time.isoformat(),
            'retention_days': retention_days,
            'local_deleted': 0,
            's3_deleted': 0,
            'status': 'success'
        }
        
        # Clean up local backups
        backup_dir = Path(__file__).parent.parent / "backups"
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        if backup_dir.exists():
            for backup_file in backup_dir.glob("reddit_publisher_*.sql*"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    try:
                        backup_file.unlink()
                        cleanup_info['local_deleted'] += 1
                        logger.info("Deleted old local backup", file=str(backup_file))
                    except Exception as e:
                        logger.warning("Failed to delete local backup", file=str(backup_file), error=str(e))
        
        # Clean up S3 backups
        try:
            from app.vault_client import get_vault_client
            vault_client = get_vault_client()
            s3_secrets = vault_client.get_secret('s3')
            
            # Use AWS CLI for S3 cleanup (more reliable than boto3 for this use case)
            env = os.environ.copy()
            env.update({
                'AWS_ACCESS_KEY_ID': s3_secrets.get('access_key', ''),
                'AWS_SECRET_ACCESS_KEY': s3_secrets.get('secret_key', ''),
            })
            
            s3_bucket = s3_secrets.get('bucket', 'reddit-publisher-backups')
            s3_endpoint = s3_secrets.get('endpoint', 'sgp1.digitaloceanspaces.com')
            
            # List S3 backups older than retention period
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            list_cmd = [
                'aws', 's3', 'ls', f's3://{s3_bucket}/database-backups/',
                '--recursive', f'--endpoint-url=https://{s3_endpoint}'
            ]
            
            result = subprocess.run(list_cmd, env=env, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 4:
                            backup_date = parts[0]
                            backup_key = parts[3]
                            
                            if backup_date < cutoff_date_str:
                                delete_cmd = [
                                    'aws', 's3', 'rm', f's3://{s3_bucket}/{backup_key}',
                                    f'--endpoint-url=https://{s3_endpoint}'
                                ]
                                
                                delete_result = subprocess.run(delete_cmd, env=env, capture_output=True, text=True, timeout=60)
                                
                                if delete_result.returncode == 0:
                                    cleanup_info['s3_deleted'] += 1
                                    logger.info("Deleted old S3 backup", key=backup_key)
                                else:
                                    logger.warning("Failed to delete S3 backup", key=backup_key, error=delete_result.stderr)
            
        except Exception as e:
            logger.warning("Failed to clean up S3 backups", error=str(e))
        
        cleanup_info['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            "Backup cleanup completed",
            duration=cleanup_info['duration_seconds'],
            local_deleted=cleanup_info['local_deleted'],
            s3_deleted=cleanup_info['s3_deleted']
        )
        
        return cleanup_info
        
    except Exception as e:
        error_msg = f"Cleanup task failed: {str(e)}"
        logger.error("Cleanup task error", error=error_msg, exception_type=type(e).__name__)
        raise


@celery_app.task(
    bind=True,
    base=BackupTask,
    name="backup.scheduled_backup_workflow",
    max_retries=1
)
def scheduled_backup_workflow(self) -> Dict[str, Any]:
    """
    Complete backup workflow: create backup, verify it, and clean up old backups
    This is the main task that should be scheduled to run regularly
    
    Returns:
        Dict containing workflow results
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting scheduled backup workflow")
        
        workflow_info = {
            'timestamp': start_time.isoformat(),
            'steps_completed': [],
            'status': 'success'
        }
        
        # Step 1: Create backup
        logger.info("Step 1: Creating database backup")
        backup_result = create_database_backup.apply(args=[True])
        backup_info = backup_result.get()
        workflow_info['backup'] = backup_info
        workflow_info['steps_completed'].append('backup_created')
        
        # Step 2: Verify the backup (wait a bit for file system sync)
        import time
        time.sleep(5)
        
        logger.info("Step 2: Verifying backup")
        verify_result = verify_backup.apply(args=[None, False])  # Verify all local backups
        verify_info = verify_result.get()
        workflow_info['verification'] = verify_info
        workflow_info['steps_completed'].append('backup_verified')
        
        # Step 3: Clean up old backups
        logger.info("Step 3: Cleaning up old backups")
        cleanup_result = cleanup_old_backups.apply(args=[30])
        cleanup_info = cleanup_result.get()
        workflow_info['cleanup'] = cleanup_info
        workflow_info['steps_completed'].append('cleanup_completed')
        
        workflow_info['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            "Scheduled backup workflow completed successfully",
            duration=workflow_info['duration_seconds'],
            steps=workflow_info['steps_completed']
        )
        
        return workflow_info
        
    except Exception as e:
        error_msg = f"Backup workflow failed: {str(e)}"
        logger.error("Backup workflow error", error=error_msg, exception_type=type(e).__name__)
        
        # Record partial completion
        workflow_info['status'] = 'failed'
        workflow_info['error'] = error_msg
        workflow_info['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()
        
        raise Exception(error_msg)


@celery_app.task(
    bind=True,
    base=BackupTask,
    name="backup.create_vault_backup",
    max_retries=3,
    default_retry_delay=300
)
def create_vault_backup(self, upload_to_s3: bool = True) -> Dict[str, Any]:
    """
    Create a Vault secrets and configuration backup using the backup script
    
    Args:
        upload_to_s3: Whether to upload backup to S3
        
    Returns:
        Dict containing backup information
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting automated Vault backup", upload_to_s3=upload_to_s3)
        
        # Prepare environment variables for backup script
        env = os.environ.copy()
        env.update({
            'VAULT_URL': settings.vault_url,
            'VAULT_TOKEN': settings.vault_token,
            'VAULT_BACKUP_RETENTION_DAYS': '30',
        })
        
        # Add S3 configuration if available
        if upload_to_s3:
            try:
                from app.vault_client import get_vault_client
                vault_client = get_vault_client()
                s3_secrets = vault_client.get_secret('s3')
                
                env.update({
                    'S3_ACCESS_KEY': s3_secrets.get('access_key', ''),
                    'S3_SECRET_KEY': s3_secrets.get('secret_key', ''),
                    'S3_BUCKET': s3_secrets.get('bucket', 'reddit-publisher-backups'),
                    'S3_ENDPOINT': s3_secrets.get('endpoint', 'sgp1.digitaloceanspaces.com'),
                })
            except Exception as e:
                logger.warning("Failed to get S3 credentials from Vault", error=str(e))
                upload_to_s3 = False
        
        # Get script path
        script_path = Path(__file__).parent.parent / "scripts" / "backup-vault.sh"
        
        if not script_path.exists():
            raise FileNotFoundError(f"Vault backup script not found: {script_path}")
        
        # Execute backup script
        logger.info("Executing Vault backup script", script_path=str(script_path))
        
        result = subprocess.run(
            [str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes timeout
            check=True
        )
        
        # Parse backup information from script output
        backup_info = {
            'timestamp': start_time.isoformat(),
            'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
            'uploaded_to_s3': upload_to_s3,
            'script_output': result.stdout,
            'status': 'success'
        }
        
        # Extract backup information from output
        for line in result.stdout.split('\n'):
            if 'Vault backup created successfully' in line:
                if 'bytes' in line:
                    size_part = line.split('(')[1].split(' bytes')[0]
                    backup_info['vault_backup_size'] = int(size_part)
            elif 'Configuration backup created successfully' in line:
                if 'bytes' in line:
                    size_part = line.split('(')[1].split(' bytes')[0]
                    backup_info['config_backup_size'] = int(size_part)
            elif 'secrets backup completed:' in line:
                # Extract secrets count
                parts = line.split(':')[1].strip().split(',')
                if len(parts) >= 2:
                    backed_up = int(parts[0].split()[0])
                    failed = int(parts[1].split()[0])
                    backup_info['secrets_backed_up'] = backed_up
                    backup_info['secrets_failed'] = failed
        
        # Record metrics
        if 'vault_backup_size' in backup_info:
            backup_metrics.backup_size.labels(backup_type="vault").set(backup_info['vault_backup_size'])
        if 'config_backup_size' in backup_info:
            backup_metrics.backup_size.labels(backup_type="config").set(backup_info['config_backup_size'])
        
        backup_metrics.backup_duration.labels(backup_type="vault").observe(backup_info['duration_seconds'])
        backup_metrics.backup_successes.labels(backup_type="vault").inc()
        
        logger.info(
            "Vault backup completed successfully",
            duration=backup_info['duration_seconds'],
            uploaded_to_s3=upload_to_s3,
            vault_size=backup_info.get('vault_backup_size'),
            config_size=backup_info.get('config_backup_size'),
            secrets_backed_up=backup_info.get('secrets_backed_up')
        )
        
        return backup_info
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Vault backup script failed with exit code {e.returncode}: {e.stderr}"
        logger.error("Vault backup script execution failed", error=error_msg, stderr=e.stderr)
        
        backup_metrics.backup_failures.labels(backup_type="vault").inc()
        
        # Retry on script failures
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying Vault backup task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=self.default_retry_delay * (2 ** self.request.retries))
        
        raise Exception(error_msg)
        
    except subprocess.TimeoutExpired:
        error_msg = "Vault backup script timed out after 30 minutes"
        logger.error("Vault backup script timeout", error=error_msg)
        backup_metrics.backup_failures.labels(backup_type="vault").inc()
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Vault backup task failed: {str(e)}"
        logger.error("Vault backup task error", error=error_msg, exception_type=type(e).__name__)
        backup_metrics.backup_failures.labels(backup_type="vault").inc()
        raise


@celery_app.task(
    bind=True,
    base=BackupTask,
    name="backup.restore_vault_secrets",
    max_retries=2,
    default_retry_delay=60
)
def restore_vault_secrets(self, vault_file: Optional[str] = None, s3_vault_key: Optional[str] = None, test_mode: bool = False) -> Dict[str, Any]:
    """
    Restore Vault secrets from backup using the restore script
    
    Args:
        vault_file: Local vault backup file path
        s3_vault_key: S3 vault backup key
        test_mode: Whether to run in test mode (dry run)
        
    Returns:
        Dict containing restore results
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting Vault secrets restore", vault_file=vault_file, s3_vault_key=s3_vault_key, test_mode=test_mode)
        
        # Prepare environment variables
        env = os.environ.copy()
        env.update({
            'VAULT_URL': settings.vault_url,
            'VAULT_TOKEN': settings.vault_token,
        })
        
        if s3_vault_key:
            try:
                from app.vault_client import get_vault_client
                vault_client = get_vault_client()
                s3_secrets = vault_client.get_secret('s3')
                
                env.update({
                    'S3_ACCESS_KEY': s3_secrets.get('access_key', ''),
                    'S3_SECRET_KEY': s3_secrets.get('secret_key', ''),
                    'S3_BUCKET': s3_secrets.get('bucket', 'reddit-publisher-backups'),
                    'S3_ENDPOINT': s3_secrets.get('endpoint', 'sgp1.digitaloceanspaces.com'),
                })
            except Exception as e:
                logger.warning("Failed to get S3 credentials for restore", error=str(e))
                raise Exception("S3 credentials required for S3 restore")
        
        # Get script path
        script_path = Path(__file__).parent.parent / "scripts" / "restore-vault.sh"
        
        if not script_path.exists():
            raise FileNotFoundError(f"Vault restore script not found: {script_path}")
        
        # Build command arguments
        cmd_args = [str(script_path), "--yes"]  # Skip confirmation in automated mode
        
        if test_mode:
            cmd_args.append("--test")
        
        if vault_file:
            cmd_args.extend(["--vault-file", vault_file])
        elif s3_vault_key:
            cmd_args.extend(["--s3-vault-key", s3_vault_key])
        else:
            raise ValueError("Either vault_file or s3_vault_key must be provided")
        
        # Execute restore script
        logger.info("Executing Vault restore script", script_path=str(script_path), args=cmd_args)
        
        result = subprocess.run(
            cmd_args,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes timeout
            check=True
        )
        
        # Parse restore results
        restore_info = {
            'timestamp': start_time.isoformat(),
            'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
            'vault_file': vault_file,
            's3_vault_key': s3_vault_key,
            'test_mode': test_mode,
            'script_output': result.stdout,
            'status': 'success'
        }
        
        # Extract restore statistics from output
        for line in result.stdout.split('\n'):
            if 'secrets restore completed:' in line:
                parts = line.split(':')[1].strip().split(',')
                if len(parts) >= 2:
                    restored = int(parts[0].split()[0])
                    failed = int(parts[1].split()[0])
                    restore_info['secrets_restored'] = restored
                    restore_info['secrets_failed'] = failed
        
        logger.info(
            "Vault secrets restore completed successfully",
            duration=restore_info['duration_seconds'],
            test_mode=test_mode,
            secrets_restored=restore_info.get('secrets_restored'),
            secrets_failed=restore_info.get('secrets_failed')
        )
        
        return restore_info
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Vault restore script failed with exit code {e.returncode}: {e.stderr}"
        logger.error("Vault restore script execution failed", error=error_msg, stderr=e.stderr)
        raise Exception(error_msg)
        
    except subprocess.TimeoutExpired:
        error_msg = "Vault restore script timed out after 30 minutes"
        logger.error("Vault restore script timeout", error=error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Vault restore task failed: {str(e)}"
        logger.error("Vault restore task error", error=error_msg, exception_type=type(e).__name__)
        raise


@celery_app.task(
    bind=True,
    base=BackupTask,
    name="backup.scheduled_vault_backup_workflow",
    max_retries=1
)
def scheduled_vault_backup_workflow(self) -> Dict[str, Any]:
    """
    Complete Vault backup workflow: create backup and upload to S3
    This task should be scheduled to run regularly for Vault backups
    
    Returns:
        Dict containing workflow results
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting scheduled Vault backup workflow")
        
        workflow_info = {
            'timestamp': start_time.isoformat(),
            'steps_completed': [],
            'status': 'success'
        }
        
        # Create Vault backup
        logger.info("Creating Vault and configuration backup")
        backup_result = create_vault_backup.apply(args=[True])
        backup_info = backup_result.get()
        workflow_info['vault_backup'] = backup_info
        workflow_info['steps_completed'].append('vault_backup_created')
        
        workflow_info['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            "Scheduled Vault backup workflow completed successfully",
            duration=workflow_info['duration_seconds'],
            steps=workflow_info['steps_completed']
        )
        
        return workflow_info
        
    except Exception as e:
        error_msg = f"Vault backup workflow failed: {str(e)}"
        logger.error("Vault backup workflow error", error=error_msg, exception_type=type(e).__name__)
        
        # Record partial completion
        workflow_info['status'] = 'failed'
        workflow_info['error'] = error_msg
        workflow_info['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()
        
        raise Exception(error_msg)


# Schedule backup tasks (these will be registered with Celery Beat)
BACKUP_SCHEDULE = {
    'scheduled-backup-workflow': {
        'task': 'backup.scheduled_backup_workflow',
        'schedule': 3600.0,  # Every hour
        'options': {
            'queue': 'backup',
            'routing_key': 'backup.scheduled'
        }
    },
    'backup-verification': {
        'task': 'backup.verify_backup',
        'schedule': 21600.0,  # Every 6 hours
        'args': (None, True),  # Verify all backups including S3
        'options': {
            'queue': 'backup',
            'routing_key': 'backup.verify'
        }
    },
    'scheduled-vault-backup-workflow': {
        'task': 'backup.scheduled_vault_backup_workflow',
        'schedule': 86400.0,  # Every 24 hours (daily)
        'options': {
            'queue': 'backup',
            'routing_key': 'backup.vault'
        }
    }
}