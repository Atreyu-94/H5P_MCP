# F0 — Línea base y decisiones de transición

Estado: baseline local implementado, 2026-09-19. Base del producto: `ac10c502eec1d1c19a8c75caf86bdc5f911407c6`.
No se promueve Bun ni se modifica el MCP activo. Las limitaciones de medición y verificaciones pendientes se detallan al final; no constituyen certificación B0.

## Evidencia local

Windows 11 x64, Python 3.12.14, Node 26.7.0 y uv 0.12.17. Node es el runtime disponible de esta medición, no una certificación de Node 22/24 ni de Bun.

- Unitarias offline: 6 passed (5.03 s).
- Suite del checkout con bibliotecas aisladas: 57 passed (114.48 s).
- Construcción wheel y sdist: passed.
- Wheel instalado en un venv temporal, con tests copiados y ejecutados fuera del checkout: 57 passed (247.65 s). Esta ejecución utilizó las dependencias resueltas para el wheel, no el entorno de desarrollo del repositorio.
- Prueba de navegador del paquete `grading.h5p`: incorrecta 0, correcta 1, máximo 1, retry true, answered true, errors []. Usa el harness existente y recursos locales de Lumi/Core, no Moodle.
- `baseline-a.json` conserva muestras individuales, mediana/p95, versiones, HEAD, estado inicial, hashes del backend/fixture y 44 H5P históricos.

El benchmark usa bibliotecas de la fixture con SHA-256 verificado y almacenamiento temporal. Cada llamada arranca Node. Las muestras no representan un backend persistente ni un arranque frío del sistema operativo. Instalación limpia significa directorio runtime vacío; la caché npm no fue vaciada. Se ejecutaron otras pruebas simultáneamente: esta medición exploratoria no permite atribuir diferencias pequeñas al runtime.

Reproducción desde PowerShell en la raíz del repositorio:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_hardening.py
.venv/Scripts/python.exe -m pytest -q
uv run --with psutil==7.0.0 python tests/benchmarks/baseline.py --output exports/baseline-a.json
uv build
```

El wheel debe instalarse en un venv temporal y ejecutar una copia de tests desde fuera del checkout. `tests/tooling/browser-baseline.ps1 -OutputPath <ruta absoluta>` prepara una fixture nueva, verifica su hash, descarga Core por commit y utiliza Playwright fijado con package-lock. Requiere Chrome instalado. El informe browser-baseline.json registra la ejecución correcta de grading/retry y fórmulas en ambos feedbacks. Ya no requiere el checkout temporal de Lumi de una sesión anterior.

`baseline-a-instrumented.json` registra la segunda ejecución sin suites de pruebas simultáneas. El muestreo de RSS suma el proceso Python y descendientes cada 10 ms; puede omitir picos más cortos y contar páginas compartidas más de una vez. Handles son la suma del árbol (fds en Unix). El tiempo de adquisición del lock incluye el pequeño coste de adquirirlo, no solamente espera por otro proceso. La medición incluye el coste del propio observador.

| Operación | Mediana ms | p95 ms | RSS pico observado MiB |
|---|---:|---:|---:|
| Catálogo, 20 muestras | 515.4 | 620.3 | 176.7 |
| Esquema, 20 muestras | 499.1 | 571.1 | 176.8 |
| Preparación, 20 muestras | 678.7 | 809.8 | 197.7 |
| Exportación, 5 muestras | 996.3 | 1176.4 | 207.4 |
| Importación vacía, 5 muestras | 1335.7 | 1998.9 | 216.4 |

Lote 10: 11.12 s; lote 100 con override: 103.78 s; rechazo por defecto de 100 confirmado. Son mediciones únicas, no percentiles representativos de lotes. La contención con propietario independiente produjo 996.9 ms de adquisición del lock. Las descargas quedan separadas en setup.

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

La raíz privada del monorepo SDK declara `2.0.0-alpha.0`, mientras el paquete server del registro declara 2.0.0. Se descargó su tarball y se verificó la integridad SHA-512 indicada arriba. Exporta McpServer, InMemoryTransport, transporte stdio y tipos de Tasks. La presencia de tipos Tasks no proporciona por sí sola un store ni un ciclo de vida de trabajos.

El probe ejecutable `tests/tooling/sdk-probe.mjs` comprueba un recurso con el servidor SDK y luego conecta su cliente al MCP Python real por stdio. Skills list/get, resources/read, tamaño y digest pasan. **Client usa negociación legacy por defecto**: para esta prueba se necesita `{versionNegotiation:{mode:'auto'}}`. El primer intento legacy no anunció Skills; esto no era un fallo del servidor. Tasks no se anuncia en el MCP actual y su ciclo de vida/conformidad permanece not_run para F4/F6. Resultado en sdk-probe.json. Node de referencia fijado para B0: 22.12.0 y 24.21.0; no fueron ejecutados en F0. La consulta oficial también encontró 22.23.2, sin sustituir silenciosamente el mínimo 22.12.0 del plan.

El lock de tests/tooling pertenece solo al harness de verificación; no reemplaza el lock Lumi del producto ni anticipa el gestor del futuro producto Bun.

Fuentes: [registro server](https://registry.npmjs.org/@modelcontextprotocol/server/2.0.0), [registro TypeScript](https://registry.npmjs.org/typescript/7.0.2), [SDK](https://github.com/modelcontextprotocol/typescript-sdk), [Skills](https://github.com/modelcontextprotocol/ext-skills), [conformance](https://github.com/modelcontextprotocol/conformance).

Propuesta de compatibilidad: conservar la última release Python recuperable y documentación de rollback durante al menos dos releases estables del producto Bun. No eliminar Python antes de F4-R. Propuesta npm: `@atreyu-94/h5p-mcp`, pendiente de propiedad/disponibilidad y decisión del titular; no se publica ni reserva.

Release Please: no existe configuración versionada; solo se encontró `.github/workflows/test.yml`. Los commits de esta etapa son docs/test/chore y no introducen un mecanismo de release.

## ADR: licencias y distribución

Inspección del tgz real: versión `10.0.4-h5pmcp.efcfeebc`, metadata GPL-3.0-or-later, `package/LICENSE` contiene GPL v3 y hay 64 entradas fuente bajo `package/src/`. Su SHA-256 coincide con provenance.json. Esto verifica presencia, no suficiencia legal de la fuente correspondiente completa.

La raíz declara Apache-2.0. La fixture contiene 23 bibliotecas de terceros con licencias y avisos propios; varios metadatos carecen de licencia. No interpretarlos como permiso de redistribución. `license-inventory.json`, regenerable con tests/tooling/license-inventory.py, inventaría declaraciones transitivas, fuentes y hashes de avisos. Falta reconciliar las declaraciones ausentes y evaluar las obligaciones del conjunto antes de distribución pública.

Decisión: mantener licencias originales sin relicenciar. El propietario del proyecto decide la política de distribución, apoyado por revisión especializada cuando proceda. Antes de npm/OCI públicos: inventario completo de componentes, avisos, fuente correspondiente y procedimiento reproducible del paquete modificado; comprobar compatibilidad del conjunto y registrar aprobación. Separar procesos no elimina por sí mismo este análisis. Las pruebas locales pueden continuar.

## Inventario y limpieza

44 archivos bajo h5p_mcp/exports fueron retirados del índice preservando todos sus bytes en disco, verificados antes/después, sin reescribir historia. Sus hashes previos quedan en baseline-a.json. Ya estaban excluidos de wheel/sdist.

No hay consumidores internos de html_utils/zip_utils: búsqueda de módulos y de escape_html/as_paragraph/zip_dir encontró únicamente sus definiciones. Se conservan por ahora: no se ha descartado uso externo de esas utilidades públicas. Su eventual retirada debe documentar compatibilidad, no mezclarse con la medición.

## Límites y gates posteriores

- No se vació la caché del SO ni npm. Primera llamada e instalación limpia se nombran explícitamente según su estado; cold start físico permanece no medido. El harness conserva muestras completas, no promete precisión submuestreo.
- Skills interoperable con SDK confirmado; Tasks completo y conformance quedan para F4/F6. No extrapolar recursos/Skills a todas las herramientas.
- Node 22/24 y Bun, Linux/macOS y dependencias nativas quedan para B0.
- Comparación B/C: diferida a F3 porque esos núcleos persistentes aún no existen. Conservar corpus/scheduler equivalentes y no bloquear F0 por una implementación de F3.
- Inventario completo de avisos y fuente correspondiente antes de distribución; decisión de licencia permanece pendiente del propietario.

F0 entrega una referencia local y decisiones revisables. Promover Bun requiere B0; publicar requiere el gate de licencias. Las comprobaciones pendientes nunca se reportan como passed.
