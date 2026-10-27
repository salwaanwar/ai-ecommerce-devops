variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "ai-ecommerce"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "instance_type" {
  description = "t3.medium minimum for Kubernetes; t3.large if ELK runs on the same node"
  type        = string
  default     = "t3.medium"
}

variable "root_volume_gb" {
  type    = number
  default = 30
}

variable "allowed_admin_cidr" {
  description = "Your public IP in CIDR form, e.g. 203.0.113.10/32 (SSH + Kubernetes API)"
  type        = string
}

variable "public_key_path" {
  type    = string
  default = "~/.ssh/ecommerce-key.pub"
}
