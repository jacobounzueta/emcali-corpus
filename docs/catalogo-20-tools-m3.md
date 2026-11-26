# Catálogo Oficial de 20 Herramientas Tipadas (Módulo 3 — Melva · EMCALI)

Documentación técnica generada directamente desde `src/emcali_corpus/tools_m3.py` para validación de
esquemas Pydantic v2, control de acceso RBAC (`citizen` vs. `manager`), compuertas HITL y mitigación
de alucinaciones en el ecosistema **LangGraph + MCP (`emcali-eder-mcp`) + OpenClaw (WhatsApp)**.

## 1. Resumen Arquitectónico

- **Total de herramientas tipadas (`@tool` + Pydantic v2):** **20**
- **Herramientas para ciudadanos (`citizen`):** **16**
- **Herramientas restringidas a gerencia (`manager` / `tools.deny`):** **4**
- **Herramientas protegidas con Human-in-the-Loop (HITL):** **4**
- **Separación de capas (Ítem 3.2 vs. 3.4):**
  - Las **20 herramientas** están definidas como `@tool` de LangChain con `args_schema` en Pydantic v2
    en `src/emcali_corpus/tools_m3.py` y vinculadas directamente al grafo LangGraph (`bind_tools()`) en
    `src/emcali_corpus/agent_graph.py`.
  - El servidor MCP propio (`src/emcali_corpus/mcp_server.py`, `emcali-eder-mcp`, ítem 3.4) expone
    estas mismas 20 herramientas hacia OpenClaw/WhatsApp aplicando exactamente el mismo RBAC y HITL.
  - Catálogo interactivo en vivo disponible en `GET /api/tools/catalog`.

## 2. Mitigación de Alucinaciones con 20 Herramientas

1. **Esquemas estrictos Pydantic v2 (`args_schema`):** Cada parámetro valida tipos, rangos y valores
   permitidos (`Literal`) antes de tocar la base de datos o el motor RAG.
2. **Geolocalización estricta de Cali (`try_resolve_cali_location`):** Rechaza barrios inexistentes
   (ej. `'Manhattan'` → `BARRIO_NO_RECONOCIDO` / HTTP `400`) en lugar de asignar una comuna arbitraria.
3. **Compuerta semántica de dominio por similitud coseno (`compute_domain_relevance_score`):** Bloquea
   consultas fuera de dominio antes de invocar herramientas o RAG.
4. **RBAC por superficie mínima (`tools.deny`):** Los ciudadanos solo reciben las 16 herramientas
   ciudadanas; las 4 administrativas son invisibles/denegadas salvo rol `manager` autenticado.
5. **Compuertas HITL (`hitl_actions`):** Acciones de alto impacto (despacho de brigadas, publicación
   de mantenimientos, difusión masiva de boletines) requieren aprobación humana explícita.

## 3. Matriz Resumen de las 20 Herramientas

| # | Herramienta (`@tool`) | Categoría | Rol RBAC | HITL | Descripción |
|---|---|---|---|---|---|
| 1 | `consultar_tarifas_emcali_csv` | `general` | `citizen` | No | Consulta determinísticamente el archivo CSV de tarifas, subsidios y metas de EMCALI. |
| 2 | `consultar_indicadores_operativos_json` | `general` | `citizen` | No | Consulta determinísticamente el JSON de indicadores de infraestructura, PQR y SLAs de EMCALI. |
| 3 | `simular_factura_mensual` | `general` | `citizen` | No | Simula determinísticamente el valor mensual de la factura EMCALI usando tarifas oficiales. |
| 4 | `comparar_tarifas_trimestres` | `general` | `citizen` | No | Compara la evolución exacta de tarifas EMCALI entre 2026-Q1, 2026-Q2 y 2026-Q3. |
| 5 | `consultar_noticias_emcali` | `general` | `citizen` | No | Consulta noticias recientes y boletines oficiales scrapeados de emcali.com.co. |
| 6 | `listar_mantenimientos_activos` | `general` | `citizen` | No | Lista los puntos de mantenimiento y reparación georreferenciados en Cali. |
| 7 | `consultar_afectacion_por_barrio` | `general` | `citizen` | No | Verifica mantenimientos oficiales y reportes ciudadanos de fallas en un barrio de Cali. |
| 8 | `suscribir_boletin_mantenimientos` | `general` | `citizen` | No | Suscribe al ciudadano al boletín diario de noticias y mantenimientos de OpenClaw. |
| 9 | `radicar_pqrs_ciudadano` | `general` | `citizen` | Sí (`HITL`) | Radica una PQRS oficial de EMCALI (contrato para clientes o cédula para no clientes). |
| 10 | `reportar_falla_servicio` | `general` | `citizen` | No | Registra una falla de servicio en Cali y actualiza las banderas de hotspots para brigadas. |
| 11 | `consultar_estado_radicado` | `general` | `citizen` | No | Consulta el estado actual de un radicado PQRS o reporte de falla por su código. |
| 12 | `listar_mis_radicados` | `general` | `citizen` | No | Lista todas las PQRS y reportes de fallas asociados a un número de contrato o cédula. |
| 13 | `buscar_corpus_institucional_qdrant` | `general` | `citizen` | No | Recupera fragmentos verificados del corpus EMCALI en Qdrant con búsqueda híbrida y citas. |
| 14 | `consultar_canales_y_puntos_atencion` | `general` | `citizen` | No | Devuelve los canales oficiales de atención presencial, telefónica y digital de EMCALI. |
| 15 | `guardar_preferencia_usuario` | `general` | `citizen` | No | Guarda un dato del perfil del usuario en el Store persistente de largo plazo. |
| 16 | `consultar_perfil_memoria_usuario` | `general` | `citizen` | No | Lee de forma auditable las preferencias y perfil almacenado del usuario. |
| 17 | `activar_punto_mantenimiento` | `general` | `manager` (`tools.deny`) | Sí (`HITL`) | [SOLO GESTIÓN EMCALI] Activa un punto de mantenimiento en vivo sobre el mapa de Cali. |
| 18 | `asignar_brigada_reparacion` | `general` | `manager` (`tools.deny`) | Sí (`HITL`) | [SOLO GESTIÓN EMCALI] Despacha una brigada a un hotspot de fallas y lo activa en el mapa. |
| 19 | `gestionar_estado_pqrs` | `general` | `manager` (`tools.deny`) | Sí (`HITL`) | [SOLO GESTIÓN EMCALI] Actualiza el estado operativo de un radicado PQRS. |
| 20 | `generar_resumen_ejecutivo_operaciones` | `general` | `manager` (`tools.deny`) | No | [SOLO GESTIÓN EMCALI] Genera KPIs en vivo de PQRS, fallas, hotspots y mantenimientos. |

## 4. Especificación Detallada de Parámetros (Pydantic v2)

### 1. `consultar_tarifas_emcali_csv`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Consulta determinísticamente el archivo CSV de tarifas, subsidios y metas de EMCALI.
- **Parámetros Pydantic v2:**
  - `servicio` (`string`, opcional, default='todos'): Servicio público a consultar en el CSV.
  - `estrato` (`integer | null`, opcional, default=None): Filtrar por estrato específico (1 a 6, o 0 para Comercial/Industrial).
  - `segmento` (`string`, opcional, default='todos'): Segmento tarifario a consultar.
  - `trimestre` (`string`, opcional, default='2026-Q3'): Trimestre de consulta (por defecto 2026-Q3 o 'todos').

### 2. `consultar_indicadores_operativos_json`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Consulta determinísticamente el JSON de indicadores de infraestructura, PQR y SLAs
de EMCALI.
- **Parámetros Pydantic v2:**
  - `servicio` (`string`, opcional, default='todos'): Servicio o área: energia, telco, proteccion-de-datos-personales, atencion-y-servicio-a-la-ciudadania o todos.
  - `trimestre` (`string`, opcional, default='todos'): Trimestre a filtrar: 2026-Q1, 2026-Q2, 2026-Q3 o todos.
  - `palabra_clave` (`string`, opcional, default=''): Término opcional para filtrar indicadores (ej. 'PQR', 'fibra', 'clientes', 'días').

### 3. `simular_factura_mensual`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Simula determinísticamente el valor mensual de la factura EMCALI usando tarifas oficiales.
- **Parámetros Pydantic v2:**
  - `servicio` (`string`, requerido): Servicio público a simular.
  - `estrato` (`integer`, requerido): Estrato (1-6) o 0 para Comercial/Industrial.
  - `consumo_mes` (`number`, requerido): Consumo mensual estimado en kWh (energía), m3 (acueducto/alcantarillado) o 1 fibra.
  - `trimestre` (`string`, opcional, default='2026-Q3'): 

### 4. `comparar_tarifas_trimestres`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Compara la evolución exacta de tarifas EMCALI entre 2026-Q1, 2026-Q2 y 2026-Q3.
- **Parámetros Pydantic v2:**
  - `servicio` (`string`, requerido): Servicio público a comparar entre trimestres.
  - `estrato` (`integer`, requerido): Estrato socioeconómico a comparar.

### 5. `consultar_noticias_emcali`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Consulta noticias recientes y boletines oficiales scrapeados de emcali.com.co.
- **Parámetros Pydantic v2:**
  - `palabra_clave` (`string`, opcional, default=''): Tema, barrio o palabra clave a buscar.
  - `solo_mantenimientos` (`boolean`, opcional, default=False): Si True, filtra únicamente noticias de reparaciones y mantenimientos.
  - `limite` (`integer`, opcional, default=6): 

### 6. `listar_mantenimientos_activos`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Lista los puntos de mantenimiento y reparación georreferenciados en Cali.
- **Parámetros Pydantic v2:**
  - `servicio` (`string`, opcional, default='todos'): 
  - `barrio` (`string`, opcional, default=''): Filtro opcional por barrio de Cali.
  - `solo_activos` (`boolean`, opcional, default=True): 

### 7. `consultar_afectacion_por_barrio`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Verifica mantenimientos oficiales y reportes ciudadanos de fallas en un barrio de Cali.
- **Parámetros Pydantic v2:**
  - `barrio` (`string`, requerido): Nombre del barrio o comuna de Cali.

### 8. `suscribir_boletin_mantenimientos`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Suscribe al ciudadano al boletín diario de noticias y mantenimientos de OpenClaw.
- **Parámetros Pydantic v2:**
  - `contacto` (`string`, requerido): Número de WhatsApp en formato E.164 (ej. +573001234567) o correo/usuario.
  - `canal` (`string`, opcional, default='whatsapp'): 
  - `nombre` (`string`, opcional, default=''): Nombre del ciudadano suscriptor.
  - `barrio_interes` (`string`, opcional, default='Todos'): Barrio prioritario para alertas.
  - `frecuencia` (`string`, opcional, default='diaria'): 

### 9. `radicar_pqrs_ciudadano`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `Sí`
- **Propósito:** Radica una PQRS oficial de EMCALI (contrato para clientes o cédula para no clientes).
- **Parámetros Pydantic v2:**
  - `tipo` (`string`, requerido): Petición, Queja, Reclamo o Sugerencia.
  - `servicio` (`string`, requerido): 
  - `identificador_tipo` (`string`, requerido): 'contrato' (cliente EMCALI) o 'cedula' (no cliente).
  - `identificador_valor` (`string`, requerido): 
  - `nombre_ciudadano` (`string`, requerido): 
  - `barrio` (`string`, requerido): 
  - `descripcion` (`string`, requerido): 
  - `telefono_e164` (`string`, opcional, default=''): 

### 10. `reportar_falla_servicio`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Registra una falla de servicio en Cali y actualiza las banderas de hotspots para brigadas.
- **Parámetros Pydantic v2:**
  - `servicio` (`string`, requerido): 
  - `identificador_tipo` (`string`, requerido): 'contrato' (cliente EMCALI) o 'cedula' (no cliente).
  - `identificador_valor` (`string`, requerido): 
  - `nombre_ciudadano` (`string`, opcional, default='Ciudadano EMCALI'): 
  - `barrio` (`string`, requerido): 
  - `direccion` (`string`, opcional, default=''): 
  - `descripcion` (`string`, requerido): 
  - `telefono_e164` (`string`, opcional, default=''): 

### 11. `consultar_estado_radicado`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Consulta el estado actual de un radicado PQRS o reporte de falla por su código.
- **Parámetros Pydantic v2:**
  - `radicado_id` (`string`, requerido): Código del radicado (ej. PQRS-2026-XXXXXX o FALLA-2026-XXXXXX).

### 12. `listar_mis_radicados`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Lista todas las PQRS y reportes de fallas asociados a un número de contrato o cédula.
- **Parámetros Pydantic v2:**
  - `identificador_valor` (`string`, requerido): Número de contrato o cédula del ciudadano.

### 13. `buscar_corpus_institucional_qdrant`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Recupera fragmentos verificados del corpus EMCALI en Qdrant con búsqueda híbrida y citas.
- **Parámetros Pydantic v2:**
  - `query` (`string`, requerido): Consulta en lenguaje natural para recuperar fragmentos del corpus de EMCALI.
  - `section_filter` (`string | null`, opcional, default=None): Filtro opcional de payload por sección (ej. 'energia', 'acueducto', 'telco', 'about').
  - `top_k` (`integer`, opcional, default=5): Cantidad máxima de fragmentos (top-k) a recuperar de Qdrant.
  - `search_mode` (`string`, opcional, default='hybrid'): Modo de recuperación: hybrid (ANN Densa + BM25 RRF), dense (solo Qdrant HNSW) o lexical.

### 14. `consultar_canales_y_puntos_atencion`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Devuelve los canales oficiales de atención presencial, telefónica y digital de EMCALI.
- **Parámetros Pydantic v2:**
  - `tipo_tramite` (`string`, opcional, default='todos'): 

### 15. `guardar_preferencia_usuario`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Guarda un dato del perfil del usuario en el Store persistente de largo plazo.
- **Parámetros Pydantic v2:**
  - `user_id` (`string`, opcional, default='ciudadano-cali'): 
  - `clave` (`string`, requerido): Ej. ubicacion_barrio, estrato_vivienda, nombre.
  - `etiqueta` (`string`, requerido): Etiqueta legible del dato.
  - `valor` (`string`, requerido): Valor a recordar en memoria de largo plazo.

### 16. `consultar_perfil_memoria_usuario`

- **Categoría:** `general` | **Rol:** `citizen` | **HITL:** `No`
- **Propósito:** Lee de forma auditable las preferencias y perfil almacenado del usuario.
- **Parámetros Pydantic v2:**
  - `user_id` (`string`, opcional, default='ciudadano-cali'): 
  - `consulta` (`string`, opcional, default=''): 

### 17. `activar_punto_mantenimiento`

- **Categoría:** `general` | **Rol:** `manager` | **HITL:** `Sí`
- **Propósito:** [SOLO GESTIÓN EMCALI] Activa un punto de mantenimiento en vivo sobre el mapa de Cali.
- **Parámetros Pydantic v2:**
  - `titulo` (`string`, requerido): 
  - `servicio` (`string`, requerido): 
  - `barrio` (`string`, requerido): 
  - `descripcion` (`string`, requerido): 
  - `brigada_asignada` (`string`, opcional, default='Brigada Operativa EMCALI'): 
  - `inicio_estimado` (`string`, opcional, default=''): 
  - `fin_estimado` (`string`, opcional, default=''): 

### 18. `asignar_brigada_reparacion`

- **Categoría:** `general` | **Rol:** `manager` | **HITL:** `Sí`
- **Propósito:** [SOLO GESTIÓN EMCALI] Despacha una brigada a un hotspot de fallas y lo activa en el mapa.
- **Parámetros Pydantic v2:**
  - `barrio` (`string`, requerido): Barrio con reportes de falla acumulados.
  - `servicio` (`string`, requerido): 
  - `brigada_asignada` (`string`, requerido): Nombre o código de la cuadrilla/brigada despachada.
  - `notas` (`string`, opcional, default=''): 

### 19. `gestionar_estado_pqrs`

- **Categoría:** `general` | **Rol:** `manager` | **HITL:** `Sí`
- **Propósito:** [SOLO GESTIÓN EMCALI] Actualiza el estado operativo de un radicado PQRS.
- **Parámetros Pydantic v2:**
  - `radicado_id` (`string`, requerido): 
  - `nuevo_estado` (`string`, requerido): 
  - `notas_gestion` (`string`, opcional, default=''): 

### 20. `generar_resumen_ejecutivo_operaciones`

- **Categoría:** `general` | **Rol:** `manager` | **HITL:** `No`
- **Propósito:** [SOLO GESTIÓN EMCALI] Genera KPIs en vivo de PQRS, fallas, hotspots y mantenimientos.
- **Parámetros Pydantic v2:**
  - `sincronizar_noticias` (`boolean`, opcional, default=False): Si True, ejecuta sincronización de noticias y mantenimientos antes del reporte.
  - `incluir_boletin` (`boolean`, opcional, default=False): 
