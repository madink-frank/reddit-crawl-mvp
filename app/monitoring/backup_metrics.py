"""
Backup-specific metrics for Reddit Ghost Publisher
Provides easy access to backup-related metrics
"""

from app.monitoring.metrics import get_metrics_collector


class BackupMetrics:
    """Wrapper class for backup-specific metrics"""
    
    def __init__(self):
        self._collector = get_metrics_collector()
    
    @property
    def backup_duration(self):
        """Backup duration histogram"""
        return self._collector.backup_duration
    
    @property
    def backup_size(self):
        """Backup size gauge"""
        return self._collector.backup_size
    
    @property
    def backup_successes(self):
        """Backup success counter"""
        return self._collector.backup_successes
    
    @property
    def backup_failures(self):
        """Backup failure counter"""
        return self._collector.backup_failures
    
    @property
    def verification_duration(self):
        """Verification duration histogram"""
        return self._collector.verification_duration
    
    @property
    def backups_verified(self):
        """Backups verified gauge"""
        return self._collector.backups_verified
    
    @property
    def verification_failures(self):
        """Verification failures gauge"""
        return self._collector.verification_failures
    
    @property
    def last_backup_timestamp(self):
        """Last backup timestamp gauge"""
        return self._collector.last_backup_timestamp
    
    @property
    def s3_upload_duration(self):
        """S3 upload duration histogram"""
        return self._collector.s3_upload_duration
    
    @property
    def s3_upload_successes(self):
        """S3 upload success counter"""
        return self._collector.s3_upload_successes
    
    @property
    def s3_upload_failures(self):
        """S3 upload failure counter"""
        return self._collector.s3_upload_failures
    
    def track_backup_success(self, backup_type: str, duration: float, size: int):
        """Track successful backup"""
        self._collector.track_backup_success(backup_type, duration, size)
    
    def track_backup_failure(self, backup_type: str):
        """Track backup failure"""
        self._collector.track_backup_failure(backup_type)
    
    def track_verification(self, duration: float, verified_count: int, failed_count: int):
        """Track backup verification"""
        self._collector.track_backup_verification(duration, verified_count, failed_count)
    
    def track_s3_upload(self, status: str, duration: float = 0.0):
        """Track S3 upload"""
        self._collector.track_s3_upload(status, duration)


# Global backup metrics instance
backup_metrics = BackupMetrics()