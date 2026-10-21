# Fuentes internas

Aqui van los PDFs institucionales que usa el agente:

| Archivo | Fuente en la BD | Contenido |
|---|---|---|
| `NUEVO-REGLAMENTO-ACADEMICO_20260525.pdf` | `reglamento_academico` | Reglamento académico Duoc UC (Res. VRA N°07/2026) |
| `calendario DuocUC.pdf` | `calendario_academico` | Calendario académico 2026 (TAV, semestres, feriados) |
| `Horas de practica duocUc.pdf` | `practicas` | Tipos de práctica (laboral / profesional), duración y requisitos |

El tipo de documento se detecta por el nombre del archivo (`reglamento`, `calendario`, `practica`),
ver `CONFIG_FUENTES` en `src/ingesta/ingest.py`. Si agregan otro PDF queda como fuente `otros`.
