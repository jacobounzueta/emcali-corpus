<!--
Gracias por contribuir a emcali-corpus.
Completa todas las secciones aplicables. Un PR con contexto insuficiente no será revisado.

Antes de abrir este PR, verifica que leíste CONSTITUTION.md.
-->

## 🏷️ Convención del título del PR

Usa un prefijo de [Conventional Commits](https://www.conventionalcommits.org/) en el título:

| Prefijo | Cuándo usarlo | Ejemplo |
|---------|---------------|---------|
| `feat:` | Nueva funcionalidad | `feat: add hybrid retriever` |
| `fix:` | Corrección de bug | `fix: handle empty metadata` |
| `docs:` | Documentación | `docs: document architecture in CONSTITUTION` |
| `refactor:` | Refactorización sin cambio de comportamiento | `refactor: split pipeline into services` |
| `test:` | Adición o corrección de pruebas | `test: cover edge cases` |
| `chore:` | Mantenimiento o configuración | `chore: update uv lock` |

> El título debe ser descriptivo, en imperativo y en una sola línea.

---

## 📌 Tipo de cambio

- [ ] **Código / Producto** 🚀 — afecta el pipeline, los modelos o la interfaz. Requiere que la suite de pruebas pase en verde.
- [ ] **Investigación / Exploración** 🔬 — prototipos o experimentos. Documenta hallazgos y reproducibilidad.
- [ ] **Documentación / Gestión** 📚 — `README.md`, `CONSTITUTION.md`, ADRs o material de sustentación.

---

## 📝 Descripción

<!-- Describe qué logra este cambio y por qué. -->

**Resuelve:** <!-- Closes #N -->

**Trazabilidad:** <!-- Enlace a la tarjeta Kanban / issue, si aplica -->

### Cambios dentro del alcance

<!-- Lista breve de los cambios principales. -->

### Fuera de alcance / otros cambios

<!-- Idealmente vacío. Si tocaste código fuera del alcance, nótalo aquí. -->

---

## 🧪 Cómo se probó

<!-- ¿Cómo verificaste que el cambio funciona? Adjunta comandos, salida o casos de prueba. -->

```bash
# Comandos ejecutados (p. ej. make check)
```

| Caso / escenario | Resultado esperado | Resultado obtenido |
|------------------|--------------------|--------------------|
|  |  |  |

---

## ✅ Checklist pre-PR

Consulta **[`CONSTITUTION.md`](../CONSTITUTION.md)** para los estándares detallados.

- [ ] **Tipado y docstrings** correctos en el código nuevo/modificado (`uv run ty check`).
- [ ] **Pruebas** ejecutadas y en verde (`make check`).
- [ ] **Lint y formato** sin errores (`make lint` / `make format`).
- [ ] **`uv.lock` actualizado** si cambió cualquier dependencia.
- [ ] **Sin secretos ni credenciales** versionados (`.env`, tokens, llaves).
- [ ] **Datos y artefactos pesados** fuera de Git (`data/raw/` y `data/processed/` respetan `.gitignore`).
- [ ] **`CONSTITUTION.md` actualizado** si hubo cambio arquitectónico, tecnológico o de proceso.
- [ ] **README / documentación** actualizados si aplica.
- [ ] **PR acotado**: un solo propósito, revisable y con historia limpia.

---

## 🔀 Integración y post-merge

- [ ] El PR fue **revisado y aprobado**.
- [ ] La **rama está actualizada** respecto a `main` (sin conflictos).
- [ ] Fusionar con **Squash & Merge**.
- [ ] **Cerrar** el issue asociado (`Closes #`).
- [ ] **Eliminar** la rama de trabajo.

---

<div align="center">
<sub>Plantilla oficial de Pull Requests · emcali-corpus</sub>
</div>
