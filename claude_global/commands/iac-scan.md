Scan COMPLETO de IaC combinando TODAS las herramientas en secuencia:
1. Trivy - seguridad (vulns, secrets, misconfig)
2. Checkov - compliance (1000+ policies)
3. tflint - lint Terraform (si hay .tf)
4. pre-commit - todos los hooks
5. Infracost - costos (si hay .tf)
Muestra resumen final con findings por severidad, compliance score, costo estimado.
$ARGUMENTS
