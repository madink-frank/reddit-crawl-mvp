# Variables for Reddit Ghost Publisher Terraform configuration

# Provider Configuration
variable "digitalocean_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "CloudFlare API token"
  type        = string
  sensitive   = true
}

# Project Configuration
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "owner" {
  description = "Owner of the infrastructure"
  type        = string
  default     = "reddit-publisher-team"
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
  default     = "sgp1"
}

# Network Configuration
variable "vpc_ip_range" {
  description = "IP range for the VPC"
  type        = string
  default     = "10.10.0.0/16"
}

variable "allowed_ssh_ips" {
  description = "List of IP addresses allowed to SSH"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# SSH Configuration
variable "ssh_key_names" {
  description = "Names of existing SSH keys in DigitalOcean"
  type        = list(string)
  default     = []
}

# Droplet Configuration
variable "droplet_image" {
  description = "Droplet image to use"
  type        = string
  default     = "docker-20-04"
}

variable "app_droplet_count" {
  description = "Number of application droplets"
  type        = number
  default     = 2
  
  validation {
    condition     = var.app_droplet_count >= 1 && var.app_droplet_count <= 10
    error_message = "App droplet count must be between 1 and 10."
  }
}

variable "app_droplet_size" {
  description = "Size of application droplets"
  type        = string
  default     = "s-2vcpu-4gb"
}

variable "monitoring_droplet_size" {
  description = "Size of monitoring droplet"
  type        = string
  default     = "s-2vcpu-2gb"
}

variable "enable_monitoring_server" {
  description = "Whether to create a dedicated monitoring server"
  type        = bool
  default     = true
}

# Database Configuration
variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15"
}

variable "postgres_size" {
  description = "PostgreSQL cluster size"
  type        = string
  default     = "db-s-1vcpu-1gb"
}

variable "postgres_node_count" {
  description = "Number of PostgreSQL nodes"
  type        = number
  default     = 1
}

variable "postgres_db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "reddit_publisher"
}

variable "postgres_user" {
  description = "PostgreSQL application user"
  type        = string
  default     = "reddit_publisher"
}

# Redis Configuration
variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "7"
}

variable "redis_size" {
  description = "Redis cluster size"
  type        = string
  default     = "db-s-1vcpu-1gb"
}

# Spaces Configuration
variable "spaces_region" {
  description = "DigitalOcean Spaces region"
  type        = string
  default     = "sgp1"
}

variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30
}

# Domain Configuration
variable "domain_name" {
  description = "Domain name for the application"
  type        = string
}

# Software Versions
variable "docker_compose_version" {
  description = "Docker Compose version to install"
  type        = string
  default     = "2.23.0"
}

# Scaling Configuration
variable "auto_scaling_enabled" {
  description = "Enable auto-scaling based on metrics"
  type        = bool
  default     = false
}

variable "min_droplets" {
  description = "Minimum number of droplets for auto-scaling"
  type        = number
  default     = 1
}

variable "max_droplets" {
  description = "Maximum number of droplets for auto-scaling"
  type        = number
  default     = 5
}

# Monitoring Configuration
variable "enable_monitoring" {
  description = "Enable monitoring and alerting"
  type        = bool
  default     = true
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for alerts"
  type        = string
  default     = ""
  sensitive   = true
}

# Backup Configuration
variable "backup_schedule" {
  description = "Cron schedule for backups"
  type        = string
  default     = "0 2 * * *"
}

variable "enable_cross_region_backup" {
  description = "Enable cross-region backup replication"
  type        = bool
  default     = false
}

# Security Configuration
variable "enable_firewall" {
  description = "Enable firewall rules"
  type        = bool
  default     = true
}

variable "enable_ddos_protection" {
  description = "Enable DDoS protection"
  type        = bool
  default     = true
}

# Cost Optimization
variable "enable_reserved_instances" {
  description = "Use reserved instances for cost optimization"
  type        = bool
  default     = false
}

variable "enable_spot_instances" {
  description = "Use spot instances for non-critical workloads"
  type        = bool
  default     = false
}

# Development Configuration
variable "enable_development_features" {
  description = "Enable development-specific features"
  type        = bool
  default     = false
}

variable "development_ssh_access" {
  description = "Allow SSH access from anywhere in development"
  type        = bool
  default     = false
}