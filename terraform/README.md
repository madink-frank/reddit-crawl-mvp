# Reddit Ghost Publisher - Infrastructure as Code

This directory contains Terraform configuration for deploying the Reddit Ghost Publisher infrastructure on DigitalOcean with CloudFlare DNS.

## Architecture Overview

The infrastructure includes:

- **DigitalOcean Droplets**: Application servers running Docker containers
- **DigitalOcean Managed PostgreSQL**: Database cluster
- **DigitalOcean Managed Redis**: Cache and message broker
- **DigitalOcean Load Balancer**: High availability and SSL termination
- **DigitalOcean Spaces**: Object storage for backups and media
- **CloudFlare**: DNS management and CDN
- **Let's Encrypt**: SSL certificates

## Prerequisites

1. **Terraform** >= 1.0
2. **DigitalOcean Account** with API token
3. **CloudFlare Account** with API token
4. **Domain Name** managed by CloudFlare
5. **SSH Key** uploaded to DigitalOcean

## Environment Setup

### 1. Configure Environment Variables

```bash
export DIGITALOCEAN_TOKEN="your-digitalocean-token"
export CLOUDFLARE_API_TOKEN="your-cloudflare-token"
```

### 2. Update Configuration Files

Edit the environment-specific configuration files:

- `environments/dev/terraform.tfvars` - Development environment
- `environments/prod/terraform.tfvars` - Production environment

Key variables to update:
- `domain_name` - Your domain name
- `ssh_key_names` - Your SSH key names in DigitalOcean
- `allowed_ssh_ips` - IP addresses allowed to SSH

### 3. Configure Backend (Optional)

For production, configure remote state storage:

```hcl
terraform {
  backend "s3" {
    bucket = "your-terraform-state-bucket"
    key    = "reddit-publisher/terraform.tfstate"
    region = "us-east-1"
  }
}
```

## Deployment

### Quick Start

Use the automated deployment script:

```bash
# Deploy development environment
./scripts/deploy-infrastructure.sh dev

# Deploy production environment
./scripts/deploy-infrastructure.sh prod --auto-approve
```

### Manual Deployment

1. **Initialize Terraform**
   ```bash
   ./scripts/terraform-manage.sh dev init
   ```

2. **Plan Deployment**
   ```bash
   ./scripts/terraform-manage.sh dev plan
   ```

3. **Apply Changes**
   ```bash
   ./scripts/terraform-manage.sh dev apply
   ```

4. **View Outputs**
   ```bash
   ./scripts/terraform-manage.sh dev output
   ```

## Environment Management

### Development Environment

- **Purpose**: Testing and development
- **Resources**: Minimal (1 droplet, small database)
- **Cost**: ~$50/month
- **Features**: Development tools enabled

```bash
# Deploy development
./scripts/terraform-manage.sh dev apply

# Destroy development
./scripts/terraform-manage.sh dev destroy
```

### Production Environment

- **Purpose**: Live application
- **Resources**: High availability (2+ droplets, larger database)
- **Cost**: ~$200/month
- **Features**: Monitoring, backups, security hardening

```bash
# Deploy production
./scripts/terraform-manage.sh prod apply

# Destroy production (careful!)
./scripts/terraform-manage.sh prod destroy
```

## Resource Overview

### Compute Resources

| Resource | Development | Production |
|----------|-------------|------------|
| App Droplets | 1x s-1vcpu-2gb | 2x s-2vcpu-4gb |
| Monitoring | 1x s-1vcpu-1gb | 1x s-2vcpu-2gb |
| Load Balancer | 1x | 1x |

### Database Resources

| Resource | Development | Production |
|----------|-------------|------------|
| PostgreSQL | db-s-1vcpu-1gb | db-s-2vcpu-4gb |
| Redis | db-s-1vcpu-1gb | db-s-1vcpu-2gb |

### Storage Resources

| Resource | Purpose | Retention |
|----------|---------|-----------|
| Backup Bucket | Database backups | 30 days |
| Media Bucket | Static files | Permanent |

## Networking

### VPC Configuration

- **Development**: 10.20.0.0/16
- **Production**: 10.10.0.0/16

### Firewall Rules

- SSH (22): Restricted to allowed IPs
- HTTP (80): Load balancer only
- HTTPS (443): Load balancer only
- Internal: Full access within VPC

### DNS Configuration

| Record | Type | Purpose |
|--------|------|---------|
| @ | A | Main domain |
| api | A | API subdomain |
| www | CNAME | WWW redirect |
| monitoring | A | Monitoring dashboard |

## Security Features

### Network Security

- VPC isolation
- Firewall rules
- SSH key authentication
- Fail2ban intrusion prevention

### SSL/TLS

- Let's Encrypt certificates
- Automatic renewal
- HTTPS redirect
- Security headers

### Access Control

- Non-root user execution
- SSH key-based authentication
- IP-based access restrictions
- Secrets management via Vault

## Monitoring and Alerting

### Metrics Collection

- Prometheus for metrics
- Grafana for dashboards
- Node exporter for system metrics
- Application metrics via /metrics endpoint

### Alerting

- Alertmanager for alert routing
- Slack integration
- Email notifications
- PagerDuty integration (configurable)

### Dashboards

- System overview
- Application metrics
- Database performance
- Queue monitoring

## Backup and Recovery

### Automated Backups

- Daily PostgreSQL dumps
- Redis snapshots
- Configuration backups
- 30-day retention

### Disaster Recovery

- Cross-region backup replication (optional)
- Infrastructure as Code for quick rebuild
- Database point-in-time recovery
- Monitoring data retention

## Cost Optimization

### Development

- Smaller instance sizes
- Single availability zone
- Reduced backup retention
- Spot instances for non-critical workloads

### Production

- Reserved instances (optional)
- Auto-scaling based on load
- Efficient resource allocation
- Cost monitoring and alerts

## Scaling

### Horizontal Scaling

```bash
# Scale application servers
terraform apply -var="app_droplet_count=4"
```

### Vertical Scaling

```bash
# Upgrade droplet size
terraform apply -var="app_droplet_size=s-4vcpu-8gb"
```

### Database Scaling

```bash
# Upgrade database
terraform apply -var="postgres_size=db-s-4vcpu-8gb"
```

## Troubleshooting

### Common Issues

1. **SSH Access Denied**
   - Check SSH key configuration
   - Verify allowed IP addresses
   - Check firewall rules

2. **SSL Certificate Issues**
   - Verify domain DNS settings
   - Check CloudFlare proxy status
   - Wait for certificate propagation

3. **Database Connection Issues**
   - Check VPC configuration
   - Verify security groups
   - Check database credentials

### Debugging Commands

```bash
# Check infrastructure status
./scripts/terraform-manage.sh prod output

# View Terraform state
./scripts/terraform-manage.sh prod show

# Check resource status
terraform state list

# Refresh state
./scripts/terraform-manage.sh prod refresh
```

### Log Locations

- **Terraform logs**: `.terraform-*/`
- **Cloud-init logs**: `/var/log/cloud-init.log` (on droplets)
- **Application logs**: `/var/log/reddit-publisher/`

## Maintenance

### Regular Tasks

1. **Update Terraform**
   ```bash
   terraform version
   # Update if needed
   ```

2. **Review Security**
   ```bash
   # Check for security updates
   terraform plan
   ```

3. **Monitor Costs**
   ```bash
   # Review DigitalOcean billing
   # Check resource utilization
   ```

4. **Backup Verification**
   ```bash
   # Test backup restoration
   # Verify backup integrity
   ```

### Updates and Patches

1. **Infrastructure Updates**
   ```bash
   # Update Terraform configuration
   git pull origin main
   ./scripts/terraform-manage.sh prod plan
   ./scripts/terraform-manage.sh prod apply
   ```

2. **Application Updates**
   ```bash
   # Deploy new application version
   ./scripts/deploy-infrastructure.sh prod --skip-terraform
   ```

## Support and Documentation

### Additional Resources

- [DigitalOcean Documentation](https://docs.digitalocean.com/)
- [CloudFlare Documentation](https://developers.cloudflare.com/)
- [Terraform Documentation](https://www.terraform.io/docs/)

### Getting Help

1. Check the troubleshooting section
2. Review Terraform plan output
3. Check cloud provider status pages
4. Consult application logs

### Contributing

1. Test changes in development environment
2. Follow infrastructure as code best practices
3. Document any configuration changes
4. Update this README as needed

## License

This infrastructure code is part of the Reddit Ghost Publisher project and follows the same license terms.