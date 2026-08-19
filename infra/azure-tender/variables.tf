variable "location" {
  type    = string
  default = "northeurope"
}
variable "name_prefix" {
  type    = string
  default = "applied-ai-tender"
}
variable "container_image" {
  type        = string
  description = "Published Tender AI container image reference"
}
variable "ollama_url" {
  type        = string
  description = "Private HTTPS endpoint for an approved Ollama-compatible runtime"
  sensitive   = true
}
