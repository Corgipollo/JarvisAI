# setup_24_7_mode.ps1 - Blindaje energetico para operacion continua 24/7.
#
# Aplicado 2026-05-24 tras descubrir que PC durmiendo 16h tumbo todos los
# daemons + schtasks + tunnel + reportes. Sleep es incompatible con un
# sistema agentic que debe operar negocio mientras el usuario duerme.
#
# Costo: ~50W extra continuos = 36 kWh/mes = ~70 MXN/mes electricidad MX.
# Beneficio: Jarvis V2 facturando, investigando, monitoreando sin pausas.
#
# Re-aplicar si Windows resetea power plan (ocurre con updates grandes).

Write-Output "=== Aplicando Modo 24/7 ==="

# 1. Activar plan Maximo Rendimiento (si existe; sino el actual)
$maxPerf = "c17da53f-fcca-412f-90b3-3b7f78151785"
powercfg /setactive $maxPerf 2>&1 | Out-Null

# 2. Eliminar timeouts AC (PC enchufada nunca duerme)
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change disk-timeout-ac 0
powercfg /change monitor-timeout-ac 30  # Monitor sí puede apagarse

# 3. Deshabilitar hibernation global (libera hiberfil.sys)
powercfg /hibernate off

# 4. Permitir wake timers (schtasks despiertan PC si llegara a dormir)
powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1

# 5. Aplicar cambios
powercfg /setactive SCHEME_CURRENT

Write-Output ""
Write-Output "=== Verificacion ==="
$standby = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "corriente alterna").Line
$hibern  = (powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE | Select-String "corriente alterna").Line
$plan    = (powercfg /getactivescheme).Trim()

Write-Output "Plan activo: $plan"
Write-Output "Standby AC : $standby"
Write-Output "Hibernate AC: $hibern"
Write-Output ""
Write-Output "Si ambos muestran 0x00000000 = Configuracion 24/7 OK"
