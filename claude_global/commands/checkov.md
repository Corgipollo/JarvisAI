Ejecuta un scan de compliance/seguridad con Checkov en el directorio actual.

Checkov tiene 1000+ policies para Terraform, Kubernetes, Docker, CloudFormation, Ansible.

Comandos disponibles:
- Terraform: `checkov -d . --framework terraform`
- Kubernetes: `checkov -d . --framework kubernetes`  
- Docker: `checkov -d . --framework dockerfile`
- Todos: `checkov -d .`
- Solo checks fallidos: `checkov -d . --compact`

Detecta el framework automaticamente segun los archivos del proyecto. Muestra resultado y sugiere fixes para checks fallidos.

$ARGUMENTS