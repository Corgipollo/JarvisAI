Ejecuta un scan de seguridad con Trivy en el directorio actual o en el path que indique el usuario.

Trivy escanea: vulnerabilidades, secretos expuestos, misconfigurations en IaC, y SBOM.

Comandos disponibles:
- Scan completo: `trivy fs --scanners vuln,secret,misconfig .`
- Solo vulnerabilidades: `trivy fs --scanners vuln .`
- Solo secretos: `trivy fs --scanners secret .`
- Imagen Docker: `trivy image NOMBRE_IMAGEN`
- Severity critica: `trivy fs --severity CRITICAL,HIGH .`

Ejecuta el scan mas apropiado segun el contexto. Si hay archivos Terraform, usa misconfig. Si hay Dockerfile, escanea la imagen. Si no se especifica, haz scan completo.

Muestra el resultado y si hay findings criticos, sugiere como corregirlos.

$ARGUMENTS