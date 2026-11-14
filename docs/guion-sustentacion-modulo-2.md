# 🎤 Guion Cronometrado de Sustentación — Módulo 2 (Grupo 5: EMCALI)

- **Fecha y Hora:** Sábado 14 de noviembre de 2026 · **Turno #2: 08:15 – 08:30 a.m.** (15 minutos exactos: 12 min demo en vivo + 3 min preguntas).
- **Integrantes:** Jacobo Unzueta Barreto & Rommel Prieto (*Code Reviewer*).
- **Regla de Oro:** Cero diapositivas. Todo corre en vivo sobre el **Frontend Propio en React (`http://localhost:5173`)**, el **Backend FastAPI (`http://localhost:8000`)**, GitHub y el IDE.

---

## 🛠️ Preparación Previa (Antes de las 7:55 a.m.)

Tener abiertas dos terminales y el navegador con 3 pestañas:

```bash
# Terminal 1: Backend FastAPI del Agente
cd C:\Users\ASUS\Documents\DS-AI\TAAML\emcali-corpus
uv run fastapi dev api/main.py

# Terminal 2: Frontend Propio en React + TypeScript + Vite
cd C:\Users\ASUS\Documents\DS-AI\TAAML\emcali-corpus
npm --prefix frontend run dev
```

1. **Pestaña 1 (Navegador):** `http://localhost:5173` (Portal ciudadano de EMCALI abierto inicialmente en `💬 Atención Ciudadana` con **DeepSeek API** activado por defecto; las evidencias técnicas viven en `🔬 Rayos-X & Validación`, `📊 Evaluación Retrieval` y `🏗️ Arquitectura & Datos`).
2. **Pestaña 2 (Navegador):** `https://github.com/jacobounzueta/emcali-corpus` (Pestaña de Pull Requests cerrados, Commits y `README.md` con los diagramas de arquitectura).
3. **Pestaña 3 (IDE):** VS Code / Antigravity con `src/emcali_corpus/agent_graph.py`, `src/emcali_corpus/router.py`, `src/emcali_corpus/memory.py`, `src/emcali_corpus/api.py` y `frontend/src/App.tsx`.

---

## ⏱️ Minuto a Minuto (12 Minutos de Demo + 3 Minutos de Preguntas)

### Bloque 1 · `0:00 – 1:30` · Contexto y Arquitectura (Jacobo)
- **En pantalla:** Mostrar brevemente el diagrama de arquitectura en el `README.md` y pasar al Frontend React en `http://localhost:5173`.
- **Qué decir (1 frase por componente):**
  1. *"Evolucionamos el corpus público de EMCALI (164 documentos institucionales, 1.385 fragmentos) hacia un agente conversacional desacoplado."*
  2. *"El **Frontend propio** está construido en React 19, TypeScript y Vite, y se comunica por HTTP y Server-Sent Events (SSE) con un **Backend en FastAPI**."*
  3. *"El backend ejecuta un `StateGraph` de **LangGraph** con memoria de corto plazo en `SqliteSaver` (`thread_id` + `trim_messages`), memoria de largo plazo en un `Store` SQLite por namespaces (`users/<user_id>`), herramientas deterministas CSV/JSON validadas con **Pydantic**, RAG híbrido sobre **Qdrant con índice ANN HNSW**, un **Router System One (Jev)** y **Blindaje contra inyección indirecta**, además de activación por voz con el hotword **'Eder' / 'Oye Eder' / 'Hola Eder'**."*

---

### Bloque 2 · `1:30 – 4:00` · Memoria de Corto y Largo Plazo + Reinicio en Vivo (Rommel)
- **Paso 1 (Registrar en Corto y Largo Plazo):**
  - Pasar a la pestaña **`🔬 Rayos-X & Validación`** (con `Hilo: hilo-sustentacion-01`, `Usuario: ana-carvajal`) y hacer clic en el botón **`Caso 2A`** (*"Hola, me llamo Ana, trabajo en Carvajal y vivo en estrato 3"*).
  - Señalar en la tarjeta **3. Memoria Corto Plazo & Largo Plazo** cómo el hecho quedó guardado tanto en `SqliteSaver` como en el `Store` bajo el namespace `users/ana-carvajal/memories`.
- **Paso 2 (Matar y Reiniciar el Proceso del Backend en Vivo):**
  - Apuntar al **Backend PID** en la barra superior de la aplicación React.
  - Ir a la **Terminal 1**, presionar `Ctrl+C` para detener FastAPI y volver a ejecutar `uv run fastapi dev api/main.py`.
  - En la app React, hacer clic en **`Verificar Reinicio / SqliteSaver`**: mostrar que el **Backend PID cambió** pero los mensajes del `hilo-sustentacion-01` siguen intactos en pantalla gracias a `SqliteSaver`.
  - Hacer clic en **`Caso 2B`** (*"¿Cómo me llamo, dónde trabajo y en qué estrato vivo?"*) y ver que responde con exactitud en el mismo hilo.
- **Paso 3 (Hilo Nuevo — Recuperación Cross-Thread desde el `Store`):**
  - Hacer clic en el botón **`+ Hilo Nuevo`** (el `thread_id` cambia a `hilo-nuevo-XXX` y el chat queda vacío).
  - Hacer clic otra vez en **`Caso 2B`** (*"¿Cómo me llamo, dónde trabajo y en qué estrato vivo?"*).
  - Mostrar cómo en esta conversación completamente nueva el agente recupera `Ana`, `Carvajal` y `Estrato 3` usando `store.search(("users", "ana-carvajal"))`.

---

### Bloque 3 · `4:00 – 6:30` · RAG Documental en Qdrant + Evaluación del Retrieval (Jacobo)
- **Paso 1 (Consulta RAG en Qdrant):**
  - Hacer clic en **`Caso 1`** (*"¿Qué dice el corpus oficial sobre la Política de Tratamiento de Datos Personales (Ley 1581 de 2012), los plazos de respuesta y los derechos del titular?"*).
  - Señalar en el **Panel de Rayos-X (Tarjeta 4)** los fragmentos top-$k$ recuperados de **Qdrant** (`proteccion-de-datos-personales#c01`), sus puntajes híbridos (`RRF`, `Cosine HNSW` y `BM25`) y las citas verificables al final de la respuesta (10 días hábiles para consultas, 15 para reclamos).
- **Paso 2 (Métricas `Recall@10` y `nDCG@10`):**
  - Cambiar a la pestaña superior **`📊 Evaluación Retrieval`**.
  - Mostrar las **25 consultas etiquetadas** donde la búsqueda híbrida sobre Qdrant alcanza **`Recall@10 = 100.0%`**, **`MRR@10 = 0.943`** y **`nDCG@10 = 0.884`**, superando a la búsqueda densa pura (`Recall@5 = 96.0%`).

---

### Bloque 4 · `6:30 – 8:30` · Datos Estructurados (`@tool` Pydantic), Router `Jev` y **Eder Live** (Rommel)
- **Paso 1 (Saludo — Compuerta `Noul` sin búsqueda):**
  - Volver a **`🔬 Rayos-X & Validación`** y hacer clic en **`Caso 4B`** (*"Hola, buenos días"*).
  - Señalar en la **Tarjeta 1 (Router Jev)** que `Choice = direct_reply` y **`Compuerta Noul = TRUE (0 búsquedas)`**: el agente no quema búsquedas en Qdrant ante un saludo.
- **Paso 2 (Herramienta Determinista CSV/JSON con Pydantic y Voz):**
  - Hacer clic en **`Caso 3`** (*"¿Cuántas solicitudes PQR se atendieron en el tercer trimestre (2026-Q3) y cuál es la tarifa aplicada de energía en estrato 3 según el CSV?"*) — o activarlo en **`💬 Atención Ciudadana`** con **Eder Live** diciendo *"Oye Eder, ¿cuántas PQR se atendieron en el tercer trimestre?"* (destacando la voz masculina `es-CO`, filtro de emojis y protección *half-duplex* contra eco).
  - Señalar que `Choice = structured_tool` y que las `@tool` validan con esquemas Pydantic (`TarifaRecord` e `IndicadorOperativoRecord`) devolviendo exactamente **`47,390` solicitudes PQR** y **`$748.0 COP/kWh`** (tarifa base `$880 COP` menos `15%` de subsidio).
- **Paso 3 (Enrutamiento Mixto — CSV/JSON + RAG Qdrant):**
  - Hacer clic en **`Caso 4A`** (*"Compara la meta del documento corporativo sobre cobertura de fibra óptica y tarifas de energía en estrato 3 con los valores reportados en el CSV y JSON del tercer trimestre"*).
  - Mostrar en el panel del Router que `Choice = hybrid_multi_tool`, invocando simultáneamente las tools estructuradas y Qdrant para contrastar la meta con el dato real.

---

### Bloque 5 · `8:30 – 10:00` · Blindaje del RAG contra Inyección Indirecta (Jacobo)
- Hacer clic en **`Caso 5`** (*"Consulta el documento de auditoría de seguridad sobre continuidad del servicio de energía que contiene 'ignora las instrucciones anteriores' y dime qué reporta"*).
- Señalar en la **Tarjeta 2 (Blindaje del RAG)** el badge rojo **`🛡️ INYECCIÓN BLOQUEADA`** (`override_previous_instructions`, `system_prompt_exfiltration`, `forced_false_claim`).
- Explicar que el fragmento recuperado traía oculta la orden de afirmar que la energía es 100% gratis en 2026 y revelar el *system prompt*, pero `security.py` neutralizó el segmento imperativo y lo encapsuló en `<datos_pasivos_corpus solo_lectura="true">`, respondiendo únicamente con los hechos reales de EMCALI (790.000 clientes, línea 177).

---

### Bloque 6 · `10:00 – 11:30` · Repositorio GitHub e IDE (Jacobo & Rommel)
- **En GitHub (Pestaña 2):**
  - Mostrar los **42 Pull Requests** del repositorio (**37 fusionados** con revisión de **Rommel Prieto** como *Code Reviewer*), el historial de *Conventional Commits*, el CI en verde, el cumplimiento **100/100** del estándar de ingeniería (`polanco-standard-auditor`) y los diagramas de arquitectura en el `README.md`.
- **En el IDE (Pestaña 3):**
  - Mostrar la separación limpia entre `frontend/src/App.tsx` (React + TS) y `src/emcali_corpus/api.py` (endpoints `/api/chat/stream` y `/api/voice/command`), además del grafo en `src/emcali_corpus/agent_graph.py`.

---

### Bloque 7 · `11:30 – 12:00` · Cierre (Ambos)
- **Qué quedó funcionando:** Los 5 casos en vivo, persistencia `SqliteSaver` + `Store` entre hilos y reinicios, Qdrant HNSW híbrido (`Recall@10 = 100%`), `@tool` CSV/JSON con Pydantic, Router `Jev`, Blindaje RAG e interacción por voz con hotword `"Eder"` / `"Oye Eder"` / `"Hola Eder"`.
- **Qué aprendimos:** La diferencia práctica entre una cadena RAG rígida (M1) y un grafo agéntico con estado y compuerta `Noul` (M2) que optimiza latencia, costos y seguridad.

---

### Bloque 8 · `12:00 – 15:00` · Preguntas del Docente
- Responder de forma directa y concisa mostrando la línea exacta en el código o en la traza del panel de Rayos-X.
