output "container_app_name" {
  value = azurerm_container_app.api.name
}
output "deployment_state" {
  value = "deployment-ready; not deployed by Terraform validation"
}
