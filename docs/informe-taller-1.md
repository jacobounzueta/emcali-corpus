# Informe Técnico — Taller 1: Creación de la Base de Conocimiento Semántico y Sistema Q&A para EMCALI E.I.C.E. E.S.P.

- **Curso:** Técnicas Avanzadas de IA Aplicadas en Modelos de Lenguaje (2026-2S)
- **Institución:** Universidad Autónoma de Occidente (UAO) — Maestría en Inteligencia Artificial y Ciencia de Datos
- **Autores:** Jacobo Unzueta (`jacobo.unzueta@uao.edu.co`) · Rommel Prieto (`rommel.prieto@uao.edu.co`)
- **Empresa asignada:** Empresas Municipales de Cali — **EMCALI E.I.C.E. E.S.P.**
- **Repositorio:** [`https://github.com/jacobounzueta/emcali-corpus`](https://github.com/jacobounzueta/emcali-corpus)

---

## 1. Descripción del Problema

**Necesidad de un canal de comunicación automatizado, trazable y preciso para EMCALI E.I.C.E. E.S.P.**

**EMCALI E.I.C.E. E.S.P.** (Empresas Municipales de Cali, NIT `890.399.003-4`) es la empresa pública multiservicios más importante del suroccidente colombiano y una de las organizaciones líderes del Top 50 del Valle del Cauca. Presta de manera integrada tres servicios públicos esenciales en el Distrito de Santiago de Cali y municipios vecinos (como Yumbo y Puerto Tejada):

1. **Energía Eléctrica:** Más de **790.000 clientes atendidos**, más de 19.000 transformadores de distribución, más de 3.000 km de red de media y alta tensión e iniciativas de transición energética (*Hogares Energéticamente Sostenibles* con paneles solares).
2. **Acueducto y Alcantarillado:** Captación, potabilización (plantas como *La Reforma*), control de calidad hídrica y tratamiento de aguas residuales.
3. **Telecomunicaciones (Telco):** Red de fibra óptica con cobertura del **92% de Cali**, planes de internet, telefonía y televisión con soporte omnicanal 24/7.

### Problemática identificada
La información pública institucional de EMCALI se encuentra dispersa en **24 secciones y más de 470 páginas** dentro de un portal corporativo híbrido (`www.emcali.com.co`), que combina páginas estáticas en Liferay con aplicaciones dinámicas en React alojadas en `portalemcali.onrender.com`. Cuando un ciudadano busca respuestas concretas sobre:
- Tarifas de energía o acueducto,
- Canales y puntos de atención presencial (CAP, CALI, Torre EMCALI, línea `177` / `5240177`),
- Medios de pago (PSE, puntos recaudadores) y condiciones de la **Factura Digital**,
- Derechos de *Habeas Data* (Ley 1581 de 2012) y plazos legales de respuesta (10 días hábiles para consultas, 15 para reclamos), o
- Programas de sostenibilidad y transparencia,

enfrenta tiempos elevados de navegación y fragmentación documental. Un asistente conversacional tradicional sin anclaje documental corre un alto riesgo de **alucinar tarifas, teléfonos o procedimientos inexistentes**, lo cual es crítico en una entidad pública vigilada.

### Alcance definido para el sistema Q&A
- **Dentro del alcance:** Información pública oficial de carácter institucional, comercial, normativo, ambiental y de orientación al ciudadano publicada en `www.emcali.com.co`.
- **Fuera del alcance (límite transaccional y de privacidad):** Consulta de saldos individuales por número de contrato/cédula, radicación autenticada de PQRS, pasarelas de pago privadas o datos personales de suscriptores. Ante estas consultas, el sistema debe abstenerse de inventar información y redirigir al usuario a los canales oficiales verificados.

---

## 2. Planteamiento de la Solución

**Creación de un núcleo de conocimiento semántico bajo arquitectura Medallion y un sistema Q&A/Resumen/FAQ controlado por Prompt Engineering como base del futuro sistema RAG.**

La solución implementada en el paquete `emcali_corpus` se divide en dos grandes capas acopladas mediante contratos de datos explícitos:

```text
[Portal www.emcali.com.co + Iframes React]
          │
          ▼  (1. Captura educada + Playwright selectivo)
   data/raw/         ──► Capa Bronze (HTML crudo reproducible)
          │
          ▼  (2. Extractor DOM propio sin chrome/menús)
   data/processed/   ──► Capa Silver (Markdown limpio)
          │
          ▼  (3. Metadatos YAML + SHA-256 + índice JSONL)
   data/gold/        ──► Capa Gold (478 docs · 164 institucionales únicos)
          │
          ├──► Consolidación Semántica (`data/knowledge_base.md`, 54.625 palabras)
          ├──► Segmentación Híbrida (`data/chunks.jsonl`, 1.385 chunks semánticos)
          │
          ▼  (4. Orquestación LangChain + DeepSeek V4.1 Flash)
   ┌──────────────────────────────────────────────────────────────┐
   │  Tareas LLM:  [1] Q&A Citado   [2] Resumen   [3] FAQ         │
   │  Interfaz interactiva en Streamlit + CLI + Suite 22 pruebas  │
   └──────────────────────────────────────────────────────────────┘
```

En esta **Fase 1 (Módulo 1)**, aprovechamos la ventana de contexto de **1 millón de tokens** de **DeepSeek V4.1 Flash (`deepseek-flash`)** para inyectar el corpus institucional consolidado limpio (`164` documentos únicos, `54.625` palabras ≈ `75.000` tokens) directamente en el *System Prompt*, gobernado por reglas estrictas de anclaje (*grounding*) y citación obligatoria de URLs oficiales.

---

## 3. Preparación de los Datos (Scraping, Limpieza y Chunking)

### 3.1. Descubrimiento y Captura Híbrida (`discovery.py`, `fetching.py`, `rendering.py`)
1. **Respeto a `robots.txt` y cortesía HTTP:** Se implementó `HttpClient` sobre `requests` con verificación previa de `robots.txt`, `User-Agent` académico identificable (`EMCALI-Corpus/0.1`), reintentos exponenciales y *throttling* mínimo de `0.75 s` entre peticiones.
2. **Descubrimiento vía Sitemap (ADR 0004):** Se recorrió `https://www.emcali.com.co/sitemap.xml` descubriendo `587` URLs. Aplicando la lista de exclusiones de rutas privadas/transaccionales (`EXCLUDED_PATH_PREFIXES`: `/login`, `/dashboard`, `/mi-cuenta`, `/nuevo-pqrs`, formularios, etc.), quedaron **570 URLs públicas en alcance**.
3. **Resolución de Iframes React con Playwright (ADR 0002):** Las páginas principales de EMCALI devuelven un contenedor Liferay cuyo cuerpo es únicamente un `<iframe>` hacia `portalemcali.onrender.com`. Cuando `find_content_frame()` detecta este patrón, `BrowserRenderer` abre la URL en Chromium headless esperando `domcontentloaded` y la hidratación de `#root` (evitando bloqueos por `networkidle`). Las páginas estáticas (como `/w/...`) se descargan por HTTP directo sin sobrecarga de navegador.

### 3.2. Limpieza DOM y Arquitectura Medallion (`extracting.py`, `gold.py`)
- Se evaluó y descartó `trafilatura` (ADR 0003) porque eliminaba tarjetas informativas y acordeones de las *landings* de servicios públicos.
- Se construyó un **extractor DOM propio** con `BeautifulSoup` + `lxml` que elimina cabeceras, menús de navegación, pies de página, modales, scripts y botones decorativos, preservando la jerarquía semántica (`#`, `##`, `###`), listas, tablas y enlaces útiles.
- Cada documento en `data/gold/<sección>/<slug>.md` (ADR 0001 y ADR 0006) incluye *front matter* YAML con `title`, `slug`, `section`, `source_url`, `canonical_url`, `captured_at`, `render`, `word_count` y `content_sha256`.

| Métrica del Corpus Capturado | Corpus Total (`--all`) | Corpus Institucional (Sin Noticias `/w/`) | Semillas Curadas (`--curated`) |
|---|---:|---:|---:|
| **Documentos Gold** | 478 | 168 (164 únicos por SHA-256) | 20 |
| **Palabras Limpias** | 167.072 | 54.625 | 10.937 |
| **Secciones Cubiertas** | 24 | 23 | 12 |
| **Chunks Generados (`1200` / `200`)** | 3.910 | 1.385 | 212 |

### 3.3. Consolidación y Segmentación Semántica (`knowledge.py`)
Para preparar tanto el contexto consolidado del Módulo 1 como los fragmentos vectorizables del Módulo 2, se implementó una segmentación en dos etapas con `langchain-text-splitters`:
1. **División estructural por encabezados (`MarkdownHeaderTextSplitter`):** Divide cada documento respetando los niveles `#`, `##` y `###`, conservando la ruta jerárquica (`heading_path`, ej. `Tarifas de Energía > Residencial`).
2. **División recursiva por caracteres (`RecursiveCharacterTextSplitter`):** Aplica `chunk_size = 1200` caracteres y `chunk_overlap = 200` caracteres con separadores priorizados (`["\n\n", "\n", ". ", " ", ""]`), generando **1.385 chunks institucionales** almacenados en `data/chunks.jsonl` con trazabilidad completa (`chunk_id`, `section`, `slug`, `title`, `source_url`, `heading_path`, `word_count`).

---

## 4. Modelado y Diseño de Prompt Engineering

### 4.1. Selección del LLM y Orquestación en el Módulo 1 (`assistant.py`)
- **Modelo LLM:** **DeepSeek V4.1 Flash (`deepseek-flash`)** consumido mediante `langchain-deepseek` (`ChatDeepSeek`) con `temperature = 0.0` para máxima fidelidad factual.
- **Justificación técnica:** `deepseek-flash` ofrece una ventana de contexto de **1M de tokens**, baja latencia en streaming y capacidad de razonamiento configurable (`reasoning_effort` en `low`, `high`, `max`). Esto permite inyectar los 164 documentos institucionales completos (~75k tokens) en el *System Prompt* sin sufrir truncamientos.
- **Orquestación con LangChain 1.4:** Se implementó el agente conversacional con `create_agent` para el flujo interactivo en streaming y cadenas declarativas LCEL (`ChatPromptTemplate | ChatDeepSeek`) para las tareas estructuradas de **Resumen Ejecutivo**, **Generación de FAQ** y **Evaluación por lotes**.

### 4.2. Arquitectura Proyectada para el Módulo 2 (Embeddings, Vector Store y LLM)
Con miras al sistema RAG completo del Módulo 2 (donde ya no se inyectará todo el corpus en el prompt sino los $k$ fragmentos más relevantes de los `1.385` chunks institucionales o los `3.910` chunks totales con noticias):
- **Modelo de Embeddings seleccionado para el Módulo 2:** **`Qwen3-Embedding` / `nomic-embed-text-v2-moe` (vía Ollama local) o `text-embedding-3-small` / `bge-m3` (multilingüe)**. Se prioriza un modelo con alto desempeño en español en el benchmark MTEB y soporte para ventanas de hasta 8.192 tokens por chunk, capaz de capturar la semántica jurídica y técnica de servicios públicos colombianos.
- **Base de Datos Vectorial para el Módulo 2:** **Qdrant** (o **Chroma / PGVector** sobre PostgreSQL), almacenando como *payload* de cada vector los metadatos del `KnowledgeChunk` (`section`, `slug`, `source_url`, `heading_path`, `content_sha256`) para habilitar **búsqueda híbrida (densa + léxica)** y filtrado por unidad de negocio (`energia`, `acueducto`, `telco`, `transparencia`).
- **LLM para el Módulo 2 y Módulo 3:** Se mantendrá **`deepseek-flash`** vía `init_chat_model` / `ChatDeepSeek` por su soporte nativo de *Structured Outputs* (Pydantic) y *Function Calling*, complementado con `PostgresSaver` para persistencia de memoria conversacional.

### 4.3. Experimentación con Estrategias de Prompt Engineering (`prompts.py`)
Se diseñaron y compararon tres estrategias de *System Prompt* sobre el mismo corpus consolidado:

| Estrategia | Diseño Técnico | Comportamiento Observado |
|---|---|---|
| **1. `minimal_zero_shot` (Línea Base)** | Instrucción breve: *"Responde únicamente basándote en el contexto proporcionado"*. | Responde preguntas simples, pero omite las URLs oficiales de respaldo y ante preguntas capciosas (ej. pedir saldo de factura personal) da respuestas vagas sin orientar a los canales oficiales. |
| **2. `razonamiento_guiado` (Grounded CoT)** | Exige localizar primero el documento y sección de evidencia, verificar cifras literalmente y estructurar la salida en 3 bloques. | Excelente precisión en preguntas multi-documento (como cruzar directivos o indicadores de red), aunque genera respuestas ligeramente más extensas. |
| **3. `estricto_citado` (Seleccionada por defecto)** | Define rol institucional, **6 reglas inquebrantables anti-alucinación**, frase canónica de rechazo fuera de alcance, límite transaccional explícito y sección obligatoria `### Fuentes oficiales` con enlaces `[Título](URL)`. | Logra **0% de alucinaciones** en las preguntas trampa, rechaza educadamente consultas de saldos privados redirigiendo a PSE/línea 177 y cita consistentemente las URLs reales del corpus. |

---

## 5. Resultados y Análisis de la Batería de Pruebas (22 Preguntas)

Se diseñó en `src/emcali_corpus/evaluation.py` una batería de **22 preguntas de prueba** distribuidas en **9 categorías** que cubren todo el alcance definido:
1. Identidad y Gobierno Corporativo (Preguntas 1–3)
2. Servicio de Energía (Preguntas 4–6)
3. Acueducto y Alcantarillado (Preguntas 7–9)
4. Telecomunicaciones / Telco (Preguntas 10–12)
5. Atención al Ciudadano y Medios de Pago (Preguntas 13–14)
6. Factura Digital (Preguntas 15–16)
7. Protección de Datos Personales — Ley 1581 de 2012 (Preguntas 17–18)
8. Sostenibilidad y Transparencia (Preguntas 19–20)
9. Control Anti-Alucinación y Límites Transaccionales (Preguntas 21–22)

### Hallazgos principales y calidad de las respuestas
- **Fidelidad factual y citación:** El sistema extrae con exactitud nombres propios (ej. *Roger Mina* como Gerente General, gerentes de unidades estratégicas), cifras operativas (*+790.000 clientes de energía*, *92% de cobertura de fibra óptica*, *57 mil metros de cable retirado en Operación Cali sin enredos*), datos normativos (*NIT 890.399.003-4*, *10 días hábiles para consultas y 15 para reclamos de Habeas Data*) y condiciones operativas (*entrega en formato ZIP de la Factura Digital*).
- **Efectividad del control anti-alucinación:**
  - Cuando se consulta con el subconjunto `--curated` (que inicialmente no incluía `/about`), al preguntar por el nombre del Gerente General, el modelo **se abstuvo de inventar un nombre** y respondió con la cláusula exacta de seguridad, demostrando que obedece el contexto por encima de su memoria paramétrica.
  - Ante la **Pregunta 21** (solicitud de saldo con número de contrato y cédula ficticios) y la **Pregunta 22** (pregunta absurda sobre un metro subterráneo en Bogotá y vuelos internacionales de EMCALI), el modelo rechaza la premisa falsa sin alucinar y orienta al ciudadano a los servicios reales de EMCALI.

### Limitaciones identificadas en el Módulo 1 (Motivación para el Módulo 2)
1. **Costo de tokens por turno e impacto de *Lost in the Middle*:** Inyectar los 164 documentos institucionales (~54.625 palabras) en cada llamada consume ~75.000 tokens de entrada por consulta y deja fuera las 310 noticias históricas (`110.971` palabras adicionales). Con la indexación vectorial de los `1.385` chunks en el Módulo 2, solo se inyectarán los $k$ fragmentos relevantes (~2.000 tokens), reduciendo el costo y la latencia en más de un 95%.
2. **Documentos publicados únicamente como anexos PDF o imágenes:** Algunas páginas institucionales (como las tablas detalladas de tarifas por estrato en PDF o el contrato único de servicios fijos en PDF) aparecen en el HTML únicamente como enlaces de descarga (`https://www.emcali.com.co/documents/...`). El asistente entrega el enlace oficial de descarga, pero la extracción del texto interno de los PDFs queda planteada como evolución del pipeline.
