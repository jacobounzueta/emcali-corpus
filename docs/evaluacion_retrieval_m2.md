# Evaluación Cuantitativa del Retrieval en Qdrant — Módulo 2 (EMCALI)

- **Colección Qdrant:** `emcali_chunks_m2` (`1386` fragmentos indexados)
- **Índice ANN:** `HNSW (m=16, ef_construct=128, distance=Cosine, dim=384)`
- **Total de consultas etiquetadas:** `25`

## 1. Comparativa por Estrategia de Búsqueda

| Estrategia de Recuperación | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |
| :--- | :---: | :---: | :---: | :---: |
| **Híbrida (Qdrant ANN Densa + BM25 RRF)** | **100.0%** | **100.0%** | **0.927** | **0.881** |
| Densa pura (Qdrant HNSW Cosine) | 96.0% | 100.0% | 0.927 | 0.868 |
| Léxica pura (BM25 k1=1.5, b=0.75) | 96.0% | 100.0% | 0.926 | 0.893 |

## 2. Detalle por Consulta Etiquetada (Modo Híbrido RRF)

| # | Categoría | Sección Esperada | Rango 1.er Hit | Recall@10 | nDCG@10 | Top Chunk Recuperado |
|---:|---|---|:---:|:---:|:---:|---|
| 1 | Gobierno Corporativo | `about` | 1 | 100% | 0.689 | `transparencia/informacion-de-la-entidad-quienes-somos#c04` |
| 2 | Identidad y Domicilio | `proteccion-de-datos-personales` | 1 | 100% | 0.792 | `proteccion-de-datos-personales/proteccion-de-datos-personales#c05` |
| 3 | Transformación e Innovación | `about` | 3 | 100% | 0.491 | `telco/telco#c19` |
| 4 | Servicio de Energía | `energia` | 1 | 100% | 0.944 | `energia/energia#c03` |
| 5 | Trámites de Energía | `energia` | 3 | 100% | 0.532 | `atencion-y-servicio-a-la-ciudadania/reporta-una-falla#c03` |
| 6 | Tarifas de Energía | `energia` | 1 | 100% | 1.000 | `energia/tarifas-de-servicios#c02` |
| 7 | Acueducto y Agua Potable | `acueducto` | 1 | 100% | 0.990 | `acueducto/acueducto#c18` |
| 8 | Calidad del Agua y Vertimientos | `acueducto` | 1 | 100% | 0.998 | `acueducto/acueducto#c21` |
| 9 | Tarifas de Acueducto | `acueducto` | 1 | 100% | 0.909 | `acueducto/tarifas-de-acueducto#c01` |
| 10 | Telecomunicaciones Fibra Óptica | `telco` | 1 | 100% | 0.806 | `telco/telco#c03` |
| 11 | Cobertura y Contratos Telco | `telco` | 1 | 100% | 0.959 | `telco/telco#c19` |
| 12 | Operación Cali sin Enredos | `telco` | 1 | 100% | 1.000 | `telco/telco#c15` |
| 13 | Canales y Líneas de Atención | `proteccion-de-datos-personales` | 1 | 100% | 0.709 | `atencion-y-servicio-a-la-ciudadania/atencion-y-servicio-a-la-ciudadania#c04` |
| 14 | Medios de Pago Electrónicos | `atencion-y-servicio-a-la-ciudadania` | 1 | 100% | 0.952 | `atencion-y-servicio-a-la-ciudadania/metodos-de-pago#c02` |
| 15 | Factura Digital Formato ZIP | `terminos-condiciones-uso-factura-digital` | 1 | 100% | 0.962 | `terminos-condiciones-uso-factura-digital/terminos-condiciones-uso-factura-digital#c07` |
| 16 | Rechazo de Correo Factura Digital | `terminos-condiciones-uso-factura-digital` | 1 | 100% | 1.000 | `terminos-condiciones-uso-factura-digital/terminos-condiciones-uso-factura-digital#c05` |
| 17 | Plazos Ley 1581 Protección de Datos | `proteccion-de-datos-personales` | 2 | 100% | 0.652 | `atencion-y-servicio-a-la-ciudadania/repartofacturas#c04` |
| 18 | Derechos del Titular de Datos | `proteccion-de-datos-personales` | 1 | 100% | 0.999 | `proteccion-de-datos-personales/proteccion-de-datos-personales#c09` |
| 19 | Sostenibilidad y Gestión Ambiental | `sostenibilidad` | 1 | 100% | 0.861 | `sostenibilidad/sostenibilidad#c05` |
| 20 | Transparencia Misión y Visión | `transparencia` | 1 | 100% | 1.000 | `transparencia/informacion-de-la-entidad-mision-y-vision#c01` |
| 21 | Normatividad y Transparencia | `transparencia` | 1 | 100% | 0.921 | `transparencia/normatividad#c01` |
| 22 | Indicadores PQR Telecomunicaciones | `telco` | 1 | 100% | 0.958 | `indicadores-pqr/indicadores-pqr#c03` |
| 23 | Accesibilidad y Usabilidad Web | `declaracion-de-conformidad-de-accesibilidad-y-usabilidad` | 1 | 100% | 1.000 | `declaracion-de-conformidad-de-accesibilidad-y-usabilidad/declaracion-de-conformidad-de-accesibilidad-y-usabilidad#c02` |
| 24 | Notificaciones de Actos Administrativos | `notificaciones-actos-administrativos` | 1 | 100% | 0.959 | `notificaciones-actos-administrativos/notificaciones-actos-administrativos#c01` |
| 25 | Atención y Servicio a la Ciudadanía | `atencion-y-servicio-a-la-ciudadania` | 1 | 100% | 0.945 | `atencion-y-servicio-a-la-ciudadania/atencion-y-servicio-a-la-ciudadania#c02` |
