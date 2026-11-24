---
name: emcali-daily-newsletter
description: Genera y distribuye el boletín diario de noticias, mantenimientos activos y alertas de fallas de EMCALI hacia los suscriptores de WhatsApp.
permissions:
  - mcp:emcali-eder:generar_boletin_diario_emcali
  - mcp:emcali-eder:consultar_noticias_emcali
  - mcp:emcali-eder:listar_mantenimientos_activos
---

# Skill: EMCALI Daily Newsletter (Boletín Diario Operativo)

## Cuándo activar
- En ejecución programada diaria (07:00 a.m. hora Colombia) o cuando un usuario solicite *"boletín diario"*, *"resumen de mantenimientos hoy"* o *"noticias de EMCALI"*.

## Procedimiento
1. Invoca `generar_boletin_diario_emcali(barrio=<barrio_del_usuario>, sincronizar_primero=True)` desde el servidor MCP `emcali-eder`.
2. Registra el conteo de mantenimientos activos y hotspots en `memory/YYYY-MM-DD.md`.
3. Entrega el campo `markdown_digest` formateado para WhatsApp, invitando al usuario a reportar fallas o suscribir su barrio si aún no está registrado.
