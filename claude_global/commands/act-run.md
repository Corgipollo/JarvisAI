Ejecuta GitHub Actions localmente con act.

Comandos:
- Listar workflows: `act -l`
- Ejecutar todos: `act`
- Ejecutar push event: `act push`
- Ejecutar PR event: `act pull_request`
- Ejecutar job especifico: `act -j NOMBRE_JOB`
- Dry run: `act -n`

Requiere Docker running. Si Docker no esta corriendo, avisarlo.

Si no hay .github/workflows/, informar y ofrecer crear un workflow basico.

$ARGUMENTS