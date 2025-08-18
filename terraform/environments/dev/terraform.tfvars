# Development environment configuration for Reddit Ghost Publisher

# Environment
environment = "dev"
owner       = "reddit-publisher-dev-team"

# Infrastructure (smaller for development)
region                = "sgp1"
app_droplet_count     = 1
app_droplet_size      = "s-1vcpu-2gb"
monitoring_droplet_size = "s-1vcpu-1gb"

# Database (smaller for development)
postgres_version    = "15"
postgres_size      = "db-s-1vcpu-1gb"
postgres_node_count = 1
postgres_db_name   = "reddit_publisher_dev"
postgres_user      = "reddit_publisher_dev"

# Redis (smaller for development)
redis_version = "7"
redis_size   = "db-s-1vcpu-1gb"

# Storage
spaces_region         = "sgp1"
backup_retention_days = 7

# Domain (development subdomain)
domain_name = "dev.your-domain.com"

# Network
vpc_ip_range = "10.20.0.0/16"
allowed_ssh_ips = [
  "0.0.0.0/0"  # Allow from anywhere in development
]

# SSH Keys
ssh_key_names = [
  "your-dev-ssh-key-name"
]

# Features
enable_monitoring_server = true
enable_firewall         = true
enable_ddos_protection  = false  # Not needed in dev
auto_scaling_enabled    = false

# Scaling (minimal for development)
min_droplets = 1
max_droplets = 2

# Backup (less frequent in development)
backup_schedule              = "0 4 * * *"
enable_cross_region_backup   = false

# Cost optimization (use cheaper options in dev)
enable_reserved_instances = false
enable_spot_instances    = true

# Development features (enabled in development)
enable_development_features = true
development_ssh_access     = true