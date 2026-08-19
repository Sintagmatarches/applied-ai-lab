resource "azurerm_resource_group" "this" {
  name     = "${var.name_prefix}-rg"
  location = var.location
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "${var.name_prefix}-logs"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "this" {
  name                       = "${var.name_prefix}-env"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
}

resource "azurerm_container_app" "api" {
  name                         = "${var.name_prefix}-api"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"

  secret {
    name  = "ollama-url"
    value = var.ollama_url
  }
  template {
    min_replicas = 0
    max_replicas = 1
    container {
      name   = "tender-ai"
      image  = var.container_image
      cpu    = 0.5
      memory = "1Gi"
      env {
        name        = "OLLAMA_URL"
        secret_name = "ollama-url"
      }
      liveness_probe {
        transport        = "HTTP"
        port             = 8099
        path             = "/health"
        interval_seconds = 30
      }
    }
  }
  ingress {
    external_enabled = false
    target_port      = 8099
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}
