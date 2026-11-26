# MEMORY.md — Memoria Curada de Largo Plazo (Mile — EMCALI)

- **Entidad:** EMCALI E.I.C.E. E.S.P. — NIT `890.399.003-4`, sede principal CAM Torre EMCALI (Av. 2N # 10-70, Cali).
- **Línea oficial de atención:** `177` (desde Cali) o `(602) 5240177`.
- **Corpus indexado en Qdrant:** 1.385+ chunks institucionales + 310 noticias oficiales de `emcali.com.co` (`Recall@10 = 100.0%`, `nDCG@10 = 0.884`).
- **Observabilidad:** LangSmith activo en proyecto `emcali-eder-m3`.
- **Despliegue de producción:** Azure VM Ubuntu 24.04 LTS + Caddy HTTPS + OpenClaw Gateway (`bind: loopback`) + WhatsApp en vivo.
