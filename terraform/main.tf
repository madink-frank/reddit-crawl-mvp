# Main Terraform configuration for Reddit Ghost Publisher
# DigitalOcean + CloudFlare infrastructure

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.34"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.20"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
  
  # Backend configuration for state management
  backend "s3" {
    # Configure this in terraform init
    # bucket = "your-terraform-state-bucket"
    # key    = "reddit-publisher/terraform.tfstate"
    # region = "us-east-1"
  }
}

# Configure providers
provider "digitalocean" {
  token = var.digitalocean_token
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# Local variables
locals {
  project_name = "reddit-publisher"
  environment  = var.environment
  
  common_tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "terraform"
    Owner       = var.owner
  }
  
  # Resource naming convention
  name_prefix = "${local.project_name}-${local.environment}"
}

# Data sources
data "digitalocean_ssh_keys" "main" {
  filter {
    key    = "name"
    values = var.ssh_key_names
  }
}

data "cloudflare_zone" "main" {
  name = var.domain_name
}

# Generate SSH key pair for infrastructure
resource "tls_private_key" "infrastructure" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "digitalocean_ssh_key" "infrastructure" {
  name       = "${local.name_prefix}-infrastructure"
  public_key = tls_private_key.infrastructure.public_key_openssh
}

# VPC for network isolation
resource "digitalocean_vpc" "main" {
  name     = "${local.name_prefix}-vpc"
  region   = var.region
  ip_range = var.vpc_ip_range
  
  description = "VPC for ${local.project_name} ${local.environment} environment"
}

# Application Droplet
resource "digitalocean_droplet" "app" {
  count = var.app_droplet_count
  
  image    = var.droplet_image
  name     = "${local.name_prefix}-app-${count.index + 1}"
  region   = var.region
  size     = var.app_droplet_size
  vpc_uuid = digitalocean_vpc.main.id
  
  ssh_keys = concat(
    data.digitalocean_ssh_keys.main.ssh_keys[*].id,
    [digitalocean_ssh_key.infrastructure.id]
  )
  
  user_data = templatefile("${path.module}/cloud-init/app-server.yml", {
    docker_compose_version = var.docker_compose_version
    project_name          = local.project_name
    environment           = local.environment
  })
  
  tags = [
    local.project_name,
    local.environment,
    "app-server"
  ]
  
  monitoring = true
  
  lifecycle {
    create_before_destroy = true
  }
}

# Database Cluster
resource "digitalocean_database_cluster" "postgres" {
  name       = "${local.name_prefix}-postgres"
  engine     = "pg"
  version    = var.postgres_version
  size       = var.postgres_size
  region     = var.region
  node_count = var.postgres_node_count
  
  private_network_uuid = digitalocean_vpc.main.id
  
  tags = [
    local.project_name,
    local.environment,
    "database"
  ]
  
  maintenance_window {
    day  = "sunday"
    hour = "02:00:00"
  }
  
  backup_restore {
    database_name = var.postgres_db_name
  }
}

# Database
resource "digitalocean_database_db" "main" {
  cluster_id = digitalocean_database_cluster.postgres.id
  name       = var.postgres_db_name
}

# Database User
resource "digitalocean_database_user" "app" {
  cluster_id = digitalocean_database_cluster.postgres.id
  name       = var.postgres_user
}

# Redis Cluster
resource "digitalocean_database_cluster" "redis" {
  name       = "${local.name_prefix}-redis"
  engine     = "redis"
  version    = var.redis_version
  size       = var.redis_size
  region     = var.region
  node_count = 1
  
  private_network_uuid = digitalocean_vpc.main.id
  
  tags = [
    local.project_name,
    local.environment,
    "cache"
  ]
  
  maintenance_window {
    day  = "sunday"
    hour = "03:00:00"
  }
}

# Spaces bucket for backups and static files
resource "digitalocean_spaces_bucket" "backups" {
  name   = "${local.name_prefix}-backups"
  region = var.spaces_region
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    id      = "delete_old_backups"
    enabled = true
    
    expiration {
      days = var.backup_retention_days
    }
    
    noncurrent_version_expiration {
      days = 7
    }
  }
}

# Spaces bucket for media files
resource "digitalocean_spaces_bucket" "media" {
  name   = "${local.name_prefix}-media"
  region = var.spaces_region
  
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    max_age_seconds = 3000
  }
}

# Load Balancer
resource "digitalocean_loadbalancer" "main" {
  name   = "${local.name_prefix}-lb"
  region = var.region
  
  vpc_uuid = digitalocean_vpc.main.id
  
  forwarding_rule {
    entry_protocol  = "http"
    entry_port      = 80
    target_protocol = "http"
    target_port     = 80
    
    tls_passthrough = false
  }
  
  forwarding_rule {
    entry_protocol  = "https"
    entry_port      = 443
    target_protocol = "http"
    target_port     = 80
    
    tls_passthrough = false
    certificate_name = digitalocean_certificate.main.name
  }
  
  healthcheck {
    protocol               = "http"
    port                   = 80
    path                   = "/health"
    check_interval_seconds = 10
    response_timeout_seconds = 5
    unhealthy_threshold    = 3
    healthy_threshold      = 2
  }
  
  droplet_ids = digitalocean_droplet.app[*].id
  
  redirect_http_to_https = true
  
  enable_proxy_protocol = false
}

# SSL Certificate
resource "digitalocean_certificate" "main" {
  name    = "${local.name_prefix}-cert"
  type    = "lets_encrypt"
  domains = [var.domain_name, "api.${var.domain_name}"]
  
  lifecycle {
    create_before_destroy = true
  }
}

# Firewall rules
resource "digitalocean_firewall" "app" {
  name = "${local.name_prefix}-app-firewall"
  
  droplet_ids = digitalocean_droplet.app[*].id
  
  # SSH access
  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.allowed_ssh_ips
  }
  
  # HTTP/HTTPS from load balancer
  inbound_rule {
    protocol                = "tcp"
    port_range             = "80"
    source_load_balancer_uids = [digitalocean_loadbalancer.main.id]
  }
  
  # Internal communication within VPC
  inbound_rule {
    protocol         = "tcp"
    port_range       = "1-65535"
    source_addresses = [digitalocean_vpc.main.ip_range]
  }
  
  inbound_rule {
    protocol         = "udp"
    port_range       = "1-65535"
    source_addresses = [digitalocean_vpc.main.ip_range]
  }
  
  # Allow all outbound traffic
  outbound_rule {
    protocol              = "tcp"
    port_range           = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  outbound_rule {
    protocol              = "udp"
    port_range           = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# CloudFlare DNS records
resource "cloudflare_record" "main" {
  zone_id = data.cloudflare_zone.main.id
  name    = "@"
  value   = digitalocean_loadbalancer.main.ip
  type    = "A"
  ttl     = 300
  
  comment = "Main domain for ${local.project_name}"
}

resource "cloudflare_record" "api" {
  zone_id = data.cloudflare_zone.main.id
  name    = "api"
  value   = digitalocean_loadbalancer.main.ip
  type    = "A"
  ttl     = 300
  
  comment = "API subdomain for ${local.project_name}"
}

resource "cloudflare_record" "www" {
  zone_id = data.cloudflare_zone.main.id
  name    = "www"
  value   = var.domain_name
  type    = "CNAME"
  ttl     = 300
  
  comment = "WWW redirect for ${local.project_name}"
}

# CloudFlare Page Rules for caching
resource "cloudflare_page_rule" "api_cache" {
  zone_id  = data.cloudflare_zone.main.id
  target   = "api.${var.domain_name}/metrics"
  priority = 1
  
  actions {
    cache_level = "bypass"
  }
}

resource "cloudflare_page_rule" "static_cache" {
  zone_id  = data.cloudflare_zone.main.id
  target   = "${var.domain_name}/static/*"
  priority = 2
  
  actions {
    cache_level         = "cache_everything"
    edge_cache_ttl      = 86400
    browser_cache_ttl   = 86400
  }
}

# Monitoring Droplet (optional)
resource "digitalocean_droplet" "monitoring" {
  count = var.enable_monitoring_server ? 1 : 0
  
  image    = var.droplet_image
  name     = "${local.name_prefix}-monitoring"
  region   = var.region
  size     = var.monitoring_droplet_size
  vpc_uuid = digitalocean_vpc.main.id
  
  ssh_keys = concat(
    data.digitalocean_ssh_keys.main.ssh_keys[*].id,
    [digitalocean_ssh_key.infrastructure.id]
  )
  
  user_data = templatefile("${path.module}/cloud-init/monitoring-server.yml", {
    project_name = local.project_name
    environment  = local.environment
  })
  
  tags = [
    local.project_name,
    local.environment,
    "monitoring"
  ]
  
  monitoring = true
}

# CloudFlare DNS for monitoring
resource "cloudflare_record" "monitoring" {
  count = var.enable_monitoring_server ? 1 : 0
  
  zone_id = data.cloudflare_zone.main.id
  name    = "monitoring"
  value   = digitalocean_droplet.monitoring[0].ipv4_address
  type    = "A"
  ttl     = 300
  
  comment = "Monitoring server for ${local.project_name}"
}