Estima costos de infraestructura cloud con Infracost.

Analiza archivos Terraform/OpenTofu y calcula cuanto costara la infra por mes en USD.

Comandos disponibles:
- Desglose: `infracost breakdown --path .`
- Comparar cambios: `infracost diff --path .`
- Output JSON: `infracost breakdown --path . --format json`

Si no hay archivos .tf, informa que Infracost necesita Terraform configs. Muestra el costo total mensual estimado y los recursos mas caros.

$ARGUMENTS