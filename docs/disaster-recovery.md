# Disaster Recovery Guide

## Overview

This document outlines the disaster recovery procedures for the Reddit Ghost Publisher system. It covers backup strategies, restoration procedures, and step-by-step recovery processes for various failure scenarios.

## Backup Strategy

### Database Backups

**Frequency**: Hourly automated backups
**Retention**: 30 days local, 90 days in S3
**Location**: 
- Local: `./backups/`
- S3: `s3://reddit-publisher-backups/database-backups/`

**What's Backed Up**:
- Complete PostgreSQL database dump
- All tables: posts, media_files, processing_logs, token_usage, api_keys
- Schema and data
- Indexes and constraints

### Vault Secrets Backups

**Frequency**: Daily automated backups
**Retention**: 30 days local, 90 days in S3
**Location**:
- Local: `./backups/vault/`
- S3: `s3://reddit-publisher-backups/vault-backups/`

**What's Backed Up**:
- All secrets from configured paths:
  - `secret/reddit` - Reddit API credentials
  - `secret/openai` - OpenAI API keys
  - `secret/ghost` - Ghost CMS credentials
  - `secret/database` - Database connection strings
  - `secret/s3` - S3/Spaces credentials
  - `secret/langsmith` - LangSmith API keys
  - `secret/monitoring` - Monitoring credentials

### Configuration Backups

**Frequency**: Daily automated backups
**Retention**: 30 days local, 90 days in S3
**Location**:
- Local: `./backups/vault/`
- S3: `s3://reddit-publisher-backups/config-backups/`

**What's Backed Up**:
- Docker configuration files
- Terraform infrastructure code
- Application configuration
- Scripts and templates
- Migration files
- Monitoring configurations

## Recovery Scenarios

### Scenario 1: Database Corruption/Loss

**Symptoms**:
- Database connection failures
- Data inconsistency errors
- PostgreSQL service won't start

**Recovery Steps**:

1. **Stop all services**:
   ```bash
   docker-compose stop api worker-collector worker-nlp worker-publisher scheduler
   ```

2. **List available backups**:
   ```bash
   ./scripts/restore-database.sh --list
   ```

3. **Test restore (dry run)**:
   ```bash
   ./scripts/restore-database.sh --test --file backups/reddit_publisher_YYYYMMDD_HHMMSS.sql.gz
   ```

4. **Perform actual restore**:
   ```bash
   ./scripts/restore-database.sh --file backups/reddit_publisher_YYYYMMDD_HHMMSS.sql.gz
   ```

5. **Verify database integrity**:
   ```bash
   docker-compose exec postgres psql -U postgres -d reddit_publisher -c "SELECT COUNT(*) FROM posts;"
   ```

6. **Restart services**:
   ```bash
   docker-compose up -d
   ```

7. **Verify application health**:
   ```bash
   curl http://localhost:8000/health
   ```

**Recovery Time Objective (RTO)**: 30 minutes
**Recovery Point Objective (RPO)**: 1 hour

### Scenario 2: Vault Secrets Loss

**Symptoms**:
- Authentication failures with external APIs
- Vault service unavailable
- Missing or corrupted secrets

**Recovery Steps**:

1. **List available Vault backups**:
   ```bash
   ./scripts/restore-vault.sh --list
   ```

2. **Test restore (dry run)**:
   ```bash
   ./scripts/restore-vault.sh --test --vault-file backups/vault/vault_backup_YYYYMMDD_HHMMSS.json
   ```

3. **Restore Vault secrets**:
   ```bash
   ./scripts/restore-vault.sh --vault-file backups/vault/vault_backup_YYYYMMDD_HHMMSS.json
   ```

4. **Verify secrets restoration**:
   ```bash
   vault kv get secret/reddit
   vault kv get secret/openai
   vault kv get secret/ghost
   ```

5. **Restart services to pick up new secrets**:
   ```bash
   docker-compose restart
   ```

**Recovery Time Objective (RTO)**: 15 minutes
**Recovery Point Objective (RPO)**: 24 hours

### Scenario 3: Complete Infrastructure Loss

**Symptoms**:
- Server/VM completely unavailable
- All local data lost
- Need to rebuild from scratch

**Recovery Steps**:

1. **Provision new infrastructure**:
   ```bash
   cd terraform/
   terraform init
   terraform plan
   terraform apply
   ```

2. **Clone repository**:
   ```bash
   git clone https://github.com/your-org/reddit-ghost-publisher.git
   cd reddit-ghost-publisher
   ```

3. **Restore configuration from S3**:
   ```bash
   ./scripts/restore-vault.sh --s3-config-key config-backups/YYYY/MM/config_backup_YYYYMMDD_HHMMSS.tar.gz
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.production.example .env
   # Edit .env with appropriate values
   ```

5. **Start infrastructure services**:
   ```bash
   docker-compose up -d postgres redis vault
   ```

6. **Restore Vault secrets from S3**:
   ```bash
   ./scripts/restore-vault.sh --s3-vault-key vault-backups/YYYY/MM/vault_backup_YYYYMMDD_HHMMSS.json
   ```

7. **Restore database from S3**:
   ```bash
   ./scripts/restore-database.sh --s3-key database-backups/YYYY/MM/reddit_publisher_YYYYMMDD_HHMMSS.sql.gz
   ```

8. **Start application services**:
   ```bash
   docker-compose up -d
   ```

9. **Verify full system health**:
   ```bash
   ./scripts/health-check.sh
   ```

**Recovery Time Objective (RTO)**: 2 hours
**Recovery Point Objective (RPO)**: 1 hour

### Scenario 4: Configuration Drift/Corruption

**Symptoms**:
- Services failing to start
- Configuration errors
- Missing or incorrect configuration files

**Recovery Steps**:

1. **Backup current state** (if partially working):
   ```bash
   tar -czf current_config_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
     --exclude='backups' --exclude='logs' --exclude='venv' .
   ```

2. **Restore configuration from backup**:
   ```bash
   ./scripts/restore-vault.sh --config-file backups/vault/config_backup_YYYYMMDD_HHMMSS.tar.gz
   ```

3. **Review and update environment variables**:
   ```bash
   diff .env.example .env
   # Update .env as needed
   ```

4. **Restart services**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

**Recovery Time Objective (RTO)**: 20 minutes
**Recovery Point Objective (RPO)**: 24 hours

## Backup Verification

### Automated Verification

The system automatically verifies backups every 6 hours:

```bash
# Manual verification
./scripts/verify-backup.sh --all --s3 --report
```

### Manual Verification Checklist

1. **Database Backup Verification**:
   - [ ] Backup file exists and is not empty
   - [ ] Gzip integrity check passes
   - [ ] SQL structure is valid
   - [ ] Contains expected tables (posts, media_files, etc.)
   - [ ] Test restore to temporary database succeeds

2. **Vault Backup Verification**:
   - [ ] JSON file is valid
   - [ ] Contains expected secret paths
   - [ ] Secret data is not empty
   - [ ] Timestamp is recent

3. **Configuration Backup Verification**:
   - [ ] Archive extracts successfully
   - [ ] Contains expected directories and files
   - [ ] Docker configurations are present
   - [ ] Terraform files are included

## Monitoring and Alerting

### Backup Failure Alerts

**Prometheus Alerts**:
- `BackupFailed`: Backup task failed
- `BackupOld`: No successful backup in 25 hours
- `BackupVerificationFailed`: Backup verification failed

**Slack Notifications**:
- Immediate notification on backup failures
- Daily summary of backup status
- Weekly backup verification reports

### Health Checks

**Database Health**:
```bash
# Check database connectivity
docker-compose exec postgres pg_isready -U postgres

# Check table counts
docker-compose exec postgres psql -U postgres -d reddit_publisher -c "
SELECT 
  schemaname,
  tablename,
  n_tup_ins as inserts,
  n_tup_upd as updates,
  n_tup_del as deletes
FROM pg_stat_user_tables;
"
```

**Vault Health**:
```bash
# Check Vault status
vault status

# Verify secret accessibility
vault kv get secret/reddit
```

## Recovery Testing

### Monthly Recovery Drills

1. **Database Recovery Test**:
   - Restore database to test environment
   - Verify data integrity
   - Test application functionality

2. **Vault Recovery Test**:
   - Restore secrets to test Vault instance
   - Verify all secrets are accessible
   - Test application authentication

3. **Full System Recovery Test**:
   - Deploy to isolated test environment
   - Restore from backups
   - Verify end-to-end functionality

### Recovery Test Checklist

- [ ] Database restore completes without errors
- [ ] All tables have expected row counts
- [ ] Vault secrets restore successfully
- [ ] Application services start correctly
- [ ] API endpoints respond correctly
- [ ] Background tasks execute successfully
- [ ] Monitoring systems show healthy status

## Contact Information

### Emergency Contacts

**Primary On-Call**: [Your contact information]
**Secondary On-Call**: [Backup contact information]
**Infrastructure Team**: [Team contact information]

### External Dependencies

**DigitalOcean Support**: [Support contact/portal]
**CloudFlare Support**: [Support contact/portal]
**Ghost CMS Support**: [Support contact/portal]

## Recovery Time Objectives (RTO) Summary

| Scenario | RTO | RPO | Priority |
|----------|-----|-----|----------|
| Database corruption | 30 min | 1 hour | Critical |
| Vault secrets loss | 15 min | 24 hours | High |
| Configuration drift | 20 min | 24 hours | Medium |
| Complete infrastructure loss | 2 hours | 1 hour | Critical |

## Post-Recovery Actions

1. **Incident Documentation**:
   - Document the incident cause
   - Record recovery steps taken
   - Note any deviations from procedures
   - Update procedures if needed

2. **System Verification**:
   - Run full system health checks
   - Verify all integrations are working
   - Check monitoring and alerting
   - Validate backup processes

3. **Stakeholder Communication**:
   - Notify stakeholders of recovery completion
   - Provide incident summary
   - Share lessons learned
   - Update documentation

4. **Process Improvement**:
   - Review recovery procedures
   - Identify areas for improvement
   - Update automation where possible
   - Schedule follow-up testing

## Appendix

### Useful Commands

```bash
# List all backups
find ./backups -name "*.sql.gz" -o -name "*.json" -o -name "*.tar.gz" | sort

# Check backup sizes
du -sh ./backups/*

# Monitor backup processes
docker-compose logs -f worker-backup

# Check S3 backup status
aws s3 ls s3://reddit-publisher-backups/ --recursive --endpoint-url=https://sgp1.digitaloceanspaces.com

# Verify database connection
docker-compose exec postgres psql -U postgres -d reddit_publisher -c "SELECT version();"

# Check Vault status
docker-compose exec vault vault status
```

### Environment Variables Reference

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=reddit_publisher
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password

# Vault
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your_vault_token

# S3/Spaces
S3_ENDPOINT=sgp1.digitaloceanspaces.com
S3_BUCKET=reddit-publisher-backups
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key

# Backup retention
BACKUP_RETENTION_DAYS=30
VAULT_BACKUP_RETENTION_DAYS=30
```