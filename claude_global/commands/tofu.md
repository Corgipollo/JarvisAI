Ejecuta comandos de OpenTofu (fork open-source de Terraform) en el directorio actual.

Subcomandos:
- Sin args o "plan": `tofu init && tofu plan`
- "apply": `tofu init && tofu apply -auto-approve`
- "fmt": `tofu fmt -recursive`
- "validate": `tofu validate`
- "state": `tofu state list`

Misma sintaxis que Terraform pero 100% open-source (CNCF). Usa esto en lugar de Terraform si el proyecto prefiere open-source.

$ARGUMENTS