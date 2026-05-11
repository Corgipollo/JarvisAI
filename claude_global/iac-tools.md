# IaC Auto-Skill — 16 Herramientas Instaladas

> Cuando Emmanuel menciona keywords relevantes, ejecutar AUTOMATICAMENTE.
> NO preguntar, NO sugerir — EJECUTAR.
> Importado desde `~/.claude/CLAUDE.md` con `@iac-tools.md`.

## Tabla: Keyword → Tool

| Si dice... | Ejecutar | Comando |
|------------|----------|---------|
| seguridad, vulnerabilidad, scan, CVE, audit | **Trivy** | `trivy fs --scanners vuln,secret,misconfig .` |
| seguridad IaC, terraform scan, misconfig | **Checkov** | `checkov -d . --framework terraform` |
| costo, cuanto cuesta, precio cloud, billing | **Infracost** | `infracost breakdown --path .` |
| infraestructura, infra, servidor, cloud | **Terraform** | `terraform init && terraform plan` |
| infra open-source, tofu | **OpenTofu** | `tofu init && tofu plan` |
| secreto, encriptar, API key, .env seguro | **SOPS+age** | `sops --encrypt` |
| CI, pipeline, GitHub Actions, workflow test | **act** | `act -l` o `act` |
| CI programable, build, pipeline codigo | **Dagger** | `dagger call` |
| diagrama, arquitectura visual, dibujo infra | **diagrams** | Script Python con `diagrams` |
| lint terraform, validar tf, calidad HCL | **tflint** | `tflint --init && tflint .` |
| docs terraform, documentar modulos | **terraform-docs** | `terraform-docs markdown table .` |
| kubernetes, k8s, cluster, pods | **kubectl** | `kubectl get all` |
| helm, chart, package k8s | **Helm** | `helm list` |
| pre-commit, hooks, calidad codigo | **pre-commit** | `pre-commit run --all-files` |
| revisa todo, scan completo, audita | **CADENA COMPLETA** | Trivy → Checkov → tflint → pre-commit → Infracost |

## Combinaciones automaticas (multi-tool)

| Tarea compleja | Secuencia |
|----------------|-----------|
| "revisa mi proyecto" | Trivy → Checkov → tflint → pre-commit |
| "prepara deploy" | terraform fmt → validate → plan → Infracost |
| "documenta la infra" | diagrams + terraform-docs |
| "asegura los secretos" | gitleaks → SOPS + age |

## Formato obligatorio al ejecutar

```
IaC Tool: {nombre} v{version}
Comando: {comando}
Resultado: {resumen}
```