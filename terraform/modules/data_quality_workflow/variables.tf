variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "control_dataset_id" {
  type = string
}

variable "staging_dataset_id" {
  type = string
}

variable "gold_dataset_id" {
  type = string
}

variable "bronze_bucket_name" {
  type = string
}

variable "scheduler_name" {
  type = string
}

variable "cron_schedule" {
  type    = string
  default = "0 3 * * *"
}

variable "time_zone" {
  type    = string
  default = "America/Caracas"
}

variable "labels" {
  type    = map(string)
  default = {}
}
