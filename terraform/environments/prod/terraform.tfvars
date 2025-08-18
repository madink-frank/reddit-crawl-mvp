# Production environment configuration for Reddit Ghost Publisher

# Environment
environment = "prod"
owner       = "reddit-publisher-team"

# Infrastructure
region                = "sgp1"
app_droplet_count     = 2
app_droplet_size      = "s-2vcpu-4gb"
monitoring_droplet_size = "s-2vcpu-2gb"

# Database
postgres_version    = "15"
postgres_size      = "db-s-2vcpu-4gb"
postgres_node_count = 1
postgres_db_name   = "reddit_publisher"
postgres_user      = "reddit_publisher"

# Redis
redis_version = "7"
redis_size   = "db-s-1vcpu-2gb"

# Storage
spaces_region         = "sgp1"
backup_retention_days = 30

# Domain (replace with your actual domain)
domain_name = "your-domain.com"

# Network
vpc_ip_range = "10.10.0.0/16"
allowed_ssh_ips = [
  "YOUR_OFFICE_IP/32",
  "YOUR_HOME_IP/32"
]

# SSH Keys (replace with your actual SSH key names in DigitalOcean)
ssh_key_names = [
  "your-ssh-key-name"
]

# Features
enable_monitoring_server = true
enable_firewall         = true
enable_ddos_protection  = true
auto_scaling_enabled    = false

# Scaling
min_droplets = 2
max_droplets = 5

# Backup
backup_schedule              = "0 2 * * *"
enable_cross_region_backup   = false

# Cost optimization
enable_reserved_instances = false
enable_spot_instances    = false

# Development features (disabled in production)
enable_development_features = false
development_ssh_access     = false