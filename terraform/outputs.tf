# Outputs for Reddit Ghost Publisher Terraform configuration

# Network Information
output "vpc_id" {
  description = "ID of the VPC"
  value       = digitalocean_vpc.main.id
}

output "vpc_ip_range" {
  description = "IP range of the VPC"
  value       = digitalocean_vpc.main.ip_range
}

# Load Balancer Information
output "load_balancer_ip" {
  description = "IP address of the load balancer"
  value       = digitalocean_loadbalancer.main.ip
}

output "load_balancer_status" {
  description = "Status of the load balancer"
  value       = digitalocean_loadbalancer.main.status
}

# Application Servers
output "app_droplet_ids" {
  description = "IDs of application droplets"
  value       = digitalocean_droplet.app[*].id
}

output "app_droplet_ips" {
  description = "IP addresses of application droplets"
  value       = digitalocean_droplet.app[*].ipv4_address
}

output "app_droplet_private_ips" {
  description = "Private IP addresses of application droplets"
  value       = digitalocean_droplet.app[*].ipv4_address_private
}

# Database Information
output "postgres_cluster_id" {
  description = "ID of the PostgreSQL cluster"
  value       = digitalocean_database_cluster.postgres.id
}

output "postgres_host" {
  description = "PostgreSQL cluster host"
  value       = digitalocean_database_cluster.postgres.host
  sensitive   = true
}

output "postgres_port" {
  description = "PostgreSQL cluster port"
  value       = digitalocean_database_cluster.postgres.port
}

output "postgres_database" {
  description = "PostgreSQL database name"
  value       = digitalocean_database_db.main.name
}

output "postgres_user" {
  description = "PostgreSQL application user"
  value       = digitalocean_database_user.app.name
}

output "postgres_password" {
  description = "PostgreSQL application user password"
  value       = digitalocean_database_user.app.password
  sensitive   = true
}

output "postgres_connection_string" {
  description = "PostgreSQL connection string"
  value = format("postgresql://%s:%s@%s:%d/%s",
    digitalocean_database_user.app.name,
    digitalocean_database_user.app.password,
    digitalocean_database_cluster.postgres.host,
    digitalocean_database_cluster.postgres.port,
    digitalocean_database_db.main.name
  )
  sensitive = true
}

# Redis Information
output "redis_cluster_id" {
  description = "ID of the Redis cluster"
  value       = digitalocean_database_cluster.redis.id
}

output "redis_host" {
  description = "Redis cluster host"
  value       = digitalocean_database_cluster.redis.host
  sensitive   = true
}

output "redis_port" {
  description = "Redis cluster port"
  value       = digitalocean_database_cluster.redis.port
}

output "redis_password" {
  description = "Redis cluster password"
  value       = digitalocean_database_cluster.redis.password
  sensitive   = true
}

output "redis_connection_string" {
  description = "Redis connection string"
  value = format("redis://:%s@%s:%d/0",
    digitalocean_database_cluster.redis.password,
    digitalocean_database_cluster.redis.host,
    digitalocean_database_cluster.redis.port
  )
  sensitive = true
}

# Storage Information
output "backup_bucket_name" {
  description = "Name of the backup bucket"
  value       = digitalocean_spaces_bucket.backups.name
}

output "backup_bucket_endpoint" {
  description = "Endpoint of the backup bucket"
  value       = digitalocean_spaces_bucket.backups.bucket_domain_name
}

output "media_bucket_name" {
  description = "Name of the media bucket"
  value       = digitalocean_spaces_bucket.media.name
}

output "media_bucket_endpoint" {
  description = "Endpoint of the media bucket"
  value       = digitalocean_spaces_bucket.media.bucket_domain_name
}

# SSL Certificate
output "ssl_certificate_id" {
  description = "ID of the SSL certificate"
  value       = digitalocean_certificate.main.id
}

output "ssl_certificate_status" {
  description = "Status of the SSL certificate"
  value       = digitalocean_certificate.main.state
}

# DNS Information
output "domain_name" {
  description = "Main domain name"
  value       = var.domain_name
}

output "api_domain" {
  description = "API domain name"
  value       = "api.${var.domain_name}"
}

output "cloudflare_zone_id" {
  description = "CloudFlare zone ID"
  value       = data.cloudflare_zone.main.id
}

# SSH Information
output "infrastructure_ssh_private_key" {
  description = "Private SSH key for infrastructure access"
  value       = tls_private_key.infrastructure.private_key_pem
  sensitive   = true
}

output "infrastructure_ssh_public_key" {
  description = "Public SSH key for infrastructure"
  value       = tls_private_key.infrastructure.public_key_openssh
}

# Monitoring Server (if enabled)
output "monitoring_server_ip" {
  description = "IP address of monitoring server"
  value       = var.enable_monitoring_server ? digitalocean_droplet.monitoring[0].ipv4_address : null
}

output "monitoring_server_private_ip" {
  description = "Private IP address of monitoring server"
  value       = var.enable_monitoring_server ? digitalocean_droplet.monitoring[0].ipv4_address_private : null
}

# Environment Information
output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "region" {
  description = "DigitalOcean region"
  value       = var.region
}

# Resource Tags
output "common_tags" {
  description = "Common tags applied to resources"
  value       = local.common_tags
}

# Connection Information for Applications
output "database_url" {
  description = "Database URL for application configuration"
  value = format("postgresql://%s:%s@%s:%d/%s",
    digitalocean_database_user.app.name,
    digitalocean_database_user.app.password,
    digitalocean_database_cluster.postgres.host,
    digitalocean_database_cluster.postgres.port,
    digitalocean_database_db.main.name
  )
  sensitive = true
}

output "redis_url" {
  description = "Redis URL for application configuration"
  value = format("redis://:%s@%s:%d/0",
    digitalocean_database_cluster.redis.password,
    digitalocean_database_cluster.redis.host,
    digitalocean_database_cluster.redis.port
  )
  sensitive = true
}

output "celery_broker_url" {
  description = "Celery broker URL"
  value = format("redis://:%s@%s:%d/0",
    digitalocean_database_cluster.redis.password,
    digitalocean_database_cluster.redis.host,
    digitalocean_database_cluster.redis.port
  )
  sensitive = true
}

output "celery_result_backend" {
  description = "Celery result backend URL"
  value = format("redis://:%s@%s:%d/1",
    digitalocean_database_cluster.redis.password,
    digitalocean_database_cluster.redis.host,
    digitalocean_database_cluster.redis.port
  )
  sensitive = true
}

# Deployment Information
output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    environment           = var.environment
    region               = var.region
    app_servers          = length(digitalocean_droplet.app)
    database_nodes       = var.postgres_node_count
    redis_nodes          = 1
    monitoring_enabled   = var.enable_monitoring_server
    ssl_enabled          = true
    firewall_enabled     = var.enable_firewall
    backup_retention     = var.backup_retention_days
  }
}