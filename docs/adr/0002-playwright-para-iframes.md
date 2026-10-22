# ADR 0002 — Playwright para los iframes de EMCALI

- **Fecha:** 2026-10-22
- **Estado:** Aceptada

## Contexto

`www.emcali.com.co` es un portal Liferay. Sus páginas devuelven un HTML con
navegación y un `<iframe>` hacia `portalemcali.onrender.com`, una aplicación React
que renderiza el contenido en el cliente. Una petición HTTP simple obtiene menos de
100 caracteres de texto útil.

## Alternativas evaluadas

1. **Consumir la API del portal.** El *bundle* apunta a un backend, pero sus rutas
   no están documentadas y expone endpoints internos. Frágil y fuera de alcance.
2. **Extraer texto del *bundle* JavaScript.** Pierde la estructura editorial y se
   rompe con cada despliegue.
3. **Renderizar con un navegador headless.** Ejecuta la misma aplicación que ve el
   usuario y devuelve el DOM final.

## Decisión

Usar Playwright con Chromium **solo** cuando `find_content_frame()` detecta un
iframe de un host de confianza. El resto se captura con `requests`.

El renderizador:

- reutiliza un navegador y un contexto entre páginas;
- bloquea imágenes, fuentes y medios para reducir tráfico;
- espera `domcontentloaded`, la hidratación de `#root` y un tiempo de asentamiento
  (se evita `networkidle`: el portal mantiene conexiones abiertas y agotaba el
  tiempo de espera en cada página);
- permite elegir el binario con `EMCALI_CHROMIUM_PATH` y cae a canales del sistema.

## Consecuencias

- Se obtiene el contenido real de las *landings* y páginas internas.
- La captura es más lenta y requiere `playwright install chromium`.
- Las pruebas unitarias no usan navegador; el renderizado se prueba de forma
  manual/integral contra el sitio.
