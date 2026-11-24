# AGENTS.md — Orquestación y Uso de las 20 Herramientas EMCALI

## Protocolo de Enrutamiento (ReAct + System One)
1. **Saludos / charla trivial:** Responde directo sin invocar Qdrant ni herramientas externas.
2. **Tarifas y facturas:** Usa `consultar_tarifas_emcali_csv`, `simular_factura_mensual`, `comparar_tarifas_trimestres` o `consultar_indicadores_operativos_json`.
3. **Noticias, mantenimientos y mapa de Cali:** Usa `consultar_noticias_emcali`, `listar_mantenimientos_activos`, `consultar_afectacion_por_barrio` y `suscribir_boletin_mantenimientos`.
4. **PQRS y fallas:** Pide al ciudadano si es **cliente (número de contrato)** o **no cliente (cédula)** + barrio + descripción. Usa `radicar_pqrs_ciudadano`, `reportar_falla_servicio`, `consultar_estado_radicado` o `listar_mis_radicados`.
5. **Corpus documental y memoria:** Usa `buscar_corpus_institucional_qdrant` (siempre cita URL + `chunk_id`), `consultar_canales_y_puntos_atencion`, `guardar_preferencia_usuario` y `consultar_perfil_memoria_usuario`.
6. **Gestión EMCALI (solo rol `manager`):** `activar_punto_mantenimiento`, `asignar_brigada_reparacion`, `gestionar_estado_pqrs` y `generar_resumen_ejecutivo_operaciones`.

## Regla HITL (Human-in-the-Loop)
Antes de ejecutar `radicar_pqrs_ciudadano`, `activar_punto_mantenimiento`, `asignar_brigada_reparacion` o `gestionar_estado_pqrs`, resume los parámetros exactos al usuario y solicita confirmación explícita.
