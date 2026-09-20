# F0 — Línea base y decisiones de transición

Estado: ejecución parcial, 2026-09-19. Base del producto: `ac10c502eec1d1c19a8c75caf86bdc5f911407c6`.
No se promueve Bun ni se modifica el MCP activo. El gate F0 sigue abierto por los puntos indicados al final.

## Evidencia local

Windows 11 x64, Python 3.12.14, Node 26.7.0 y uv 0.12.17. Node es el runtime disponible de esta medición, no una certificación de Node 22/24 ni de Bun.

- Unitarias offline: 6 passed (5.03 s).
- Suite del checkout con bibliotecas aisladas: 57 passed (114.48 s).
- Construcción wheel y sdist: passed.
- Prueba de navegador del paquete `grading.h5p`: incorrecta 0, correcta 1, máximo 1, retry true, answered true, errors []. Usa el harness existente y recursos locales de Lumi/Core, no Moodle.
- `baseline-a.json` conserva muestras individuales, mediana/p95, versiones, HEAD, estado inicial, hashes del backend/fixture y 44 H5P históricos.

El benchmark usa bibliotecas de la fixture con SHA-256 verificado y almacenamiento temporal. Cada llamada arranca Node. Las muestras no representan un backend persistente ni un arranque frío del sistema operativo. Instalación limpia significa directorio runtime vacío; la caché npm no fue vaciada. Se ejecutaron otras pruebas simultáneamente: esta medición exploratoria no permite atribuir diferencias pequeñas al runtime.

Reproducción desde PowerShell en la raíz del repositorio:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_hardening.py
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe tests/benchmarks/baseline.py --output exports/baseline-a.json
uv build
```

El wheel debe instalarse en un venv temporal y ejecutar una copia de tests desde fuera del checkout. El browser smoke requiere los recursos especificados en su cabecera; esos directorios temporales no constituyen una dependencia reproducible distribuida. Preparar su bootstrap bloqueado antes de considerar F0.2 completamente cerrado.

## ADR: runtime y compatibilidad

Se conserva Python/Node mientras B0–F4 prueban paridad. Bun 1.4.2 es candidato, no runtime certificado. TypeScript 7.0.2 y `@modelcontextprotocol/server` 2.0.0 fueron consultados en el registro npm, sin instalarse. No usar `latest` al implementar.

Integridades observadas:

| Paquete | Integridad SHA-512 |
|---|---|
| @modelcontextprotocol/server 2.0.0 | `sha512-YhHWdHfpFMQfd0prsEnxKeS3Qz3ytIGmsS0sth4KDjnacIT7hxk6hXHkJ9KysxlkvTM+WZAtQbbcUhdoP4Hvtw==` |
| typescript 7.0.2 | `sha512-8FYau96o3NKOhbjKi/qNvG/W5jhzxkbdm5sj9AbZ/5T5sWqn3hJgLfGx27sRKZWTvyzCP8dLRBTf5tBTSRVUNA==` |

Referencias Git observadas mediante API GitHub:

| Repositorio modelcontextprotocol | Commit |
|---|---|
| typescript-sdk | `60321700871029401a2e3bed8fdf4f02c9ec3331` |
| conformance | `7169291ec0b68eb370fddcd9947313ab0d5e4156` |
| ext-skills | `0e85d4db8860a305c857f26fdede64f416675b92` |

La raíz privada del monorepo SDK declara `2.0.0-alpha.0`, mientras el paquete server del registro declara 2.0.0. No inferir el estado del paquete publicable a partir de la versión raíz. Falta inspeccionar el tarball fijado y demostrar sus APIs de Skills/Tasks con un cliente real; estos metadatos no sustituyen el spike. La consulta web de contenido por SHA falló y debe repetirse mediante checkout/descarga verificada.

Fuentes: [registro server](https://registry.npmjs.org/@modelcontextprotocol/server/2.0.0), [registro TypeScript](https://registry.npmjs.org/typescript/7.0.2), [SDK](https://github.com/modelcontextprotocol/typescript-sdk), [Skills](https://github.com/modelcontextprotocol/ext-skills), [conformance](https://github.com/modelcontextprotocol/conformance).

Propuesta de compatibilidad: conservar la última release Python recuperable y documentación de rollback durante al menos dos releases estables del producto Bun. No eliminar Python antes de F4-R. Propuesta npm: `@atreyu-94/h5p-mcp`, pendiente de propiedad/disponibilidad y decisión del titular; no se publica ni reserva.

Release Please: no existe configuración versionada; solo se encontró `.github/workflows/test.yml`. Los commits de esta etapa son docs/test/chore y no introducen un mecanismo de release.

## ADR: licencias y distribución

Inspección del tgz real: versión `10.0.4-h5pmcp.efcfeebc`, metadata GPL-3.0-or-later, `package/LICENSE` contiene GPL v3 y hay 64 entradas fuente bajo `package/src/`. Su SHA-256 coincide con provenance.json. Esto verifica presencia, no suficiencia legal de la fuente correspondiente completa.

La raíz declara Apache-2.0. La fixture contiene 23 bibliotecas de terceros con licencias y avisos propios; varios metadatos carecen de licencia. No interpretarlos como permiso de redistribución. El lock de fixture preserva los metadatos conocidos; falta reconciliar avisos de cada componente y dependencias transitivas.

Decisión: mantener licencias originales sin relicenciar. El propietario del proyecto decide la política de distribución, apoyado por revisión especializada cuando proceda. Antes de npm/OCI públicos: inventario completo de componentes, avisos, fuente correspondiente y procedimiento reproducible del paquete modificado; comprobar compatibilidad del conjunto y registrar aprobación. Separar procesos no elimina por sí mismo este análisis. Las pruebas locales pueden continuar.

## Inventario y limpieza

44 archivos bajo h5p_mcp/exports están versionados, pero se excluyen ya de wheel/sdist. Se retiran del índice preservando todos sus bytes en disco y sin reescribir historia. Sus hashes previos quedan en baseline-a.json.

No hay consumidores internos de html_utils/zip_utils: búsqueda de módulos y de escape_html/as_paragraph/zip_dir encontró únicamente sus definiciones. Se conservan por ahora: no se ha descartado uso externo de esas utilidades públicas. Su eventual retirada debe documentar compatibilidad, no mezclarse con la medición.

## Pendientes que mantienen abierto F0

- Bootstrap reproducible del navegador y logs estructurados de todas las verificaciones.
- Inspección y spike del SDK publicado, Skills/Tasks, y versiones exactas Node 22/24.
- RSS del árbol completo de procesos, handles, espera de lock bajo contención y lote 100 con override aislado; repetir medición sin suites concurrentes.
- Separar primera llamada de caché del SO; no llamar cold start a la medición actual.
- Comparación B/C: diferida a F3 porque esos núcleos persistentes aún no existen. Conservar corpus/scheduler equivalentes y no bloquear F0 por una implementación de F3.
- Inventario completo de avisos y fuente correspondiente antes de distribución; decisión de licencia permanece pendiente del propietario.

No marcar la primera etapa completa ni empezar a promover Bun mientras los pendientes técnicos propios de F0 sigan abiertos.
