Ejecuta comandos de Terraform en el directorio actual.

Subcomandos:
- Sin args o "plan": `terraform init && terraform plan`
- "apply": `terraform init && terraform apply -auto-approve`
- "fmt": `terraform fmt -recursive`
- "validate": `terraform validate`
- "destroy": `terraform destroy` (PEDIR CONFIRMACION)
- "import RECURSO ID": `terraform import RECURSO ID`
- "state": `terraform state list`
- "output": `terraform output`

Si no hay archivos .tf, pregunta si quiere crear un proyecto Terraform nuevo y genera el scaffold basico (main.tf, variables.tf, outputs.tf, providers.tf).

IMPORTANTE: Para destroy SIEMPRE pedir confirmacion a Emmanuel.

$ARGUMENTS