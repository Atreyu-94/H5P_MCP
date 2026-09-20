# B0/F1: ejecución local y gates pendientes

Fecha: 2026-09-19. Producto ampliado: `53a10b9`; CI previo verificado: `060220c`.
Repositorio y destino de todos los pushes: **Atreyu-94/H5P_MCP**, fork de
0xMarik/H5P_MCP. Oxlint es el linter ejecutado dentro de ese CI.

## Resultado local

| Comprobación | Resultado observado |
|---|---|
| Suite Python/stdio/Lumi aislada final | 101 passed, 84,60 s, Windows x64, incluidas cancelación real y deadline global de lotes |
| Corpus diferencial sobre dependencias npm | Nueve actividades, incluidos PNG, WAV, WebM y matemáticas; exportación e importación cruzada correctas |
| Corpus sobre instalación frozen de Bun | Nueve actividades, CRC nativo, UUID inválidos/duplicados, paquetes incompletos, MathDisplay ausente, no-overwrite y preparación obsoleta: passed |
| Navegador sobre paquetes Node y Bun | Nueve paquetes por runtime, cero errores; Audio y Video efectivamente decodificados/reproducidos |
| Feedback matemático y grading | En ambos runtimes: incorrecto 0/1, reintento, correcto 1/1, respuesta registrada y fórmulas visibles |
| Protocolo/proceso | EOF vacío, input excesivo, espera de EOF, terminación/reap, diez operaciones por runtime sin temporales de trabajo retenidos |
| Streams | Treinta iteraciones de 1 MiB por runtime con consumidor lento, propagación de error y muestras de memoria |
| Red explícita | Refresh Hub e instalación Audio 1.5.29 en dos stores descartables: passed con Node/Bun |
| Identidad Bun Windows | Archivo oficial SHA-256 y binario instalado idénticos, versión 1.4.2 |
| Tooling | TS 7.0.2 + tipos Bun 1.4.2 + Oxlint 1.83.0/tsgolint 7.0.2002; casos positivo/negativo pasan bajo Node y Bun |
| Higiene y lint | Guardia del índice y Oxlint del bridge pasan |

La memoria se registra como RSS/heap/external, sin atribuir RSS al heap ni deducir
ausencia de fugas en sesiones indefinidas. El producto sigue usando trabajos
aislados; no existe todavía un núcleo Bun persistente que pueda certificarse.
La cancelación se verifica con worker controlado, contención real de FileLock y
dos operaciones Lumi reales: se espera a observar archivos JS extraídos durante
importación o el archivo staging durante exportación antes de cancelar. Se exige
reap, eliminación de temporales del hijo y ausencia de publicación parcial.
No equivale a fault injection en cada syscall interna de Lumi.

## Contraste semántico

Se inspeccionaron `SemanticsEnforcer`, `ContentScanner`, `ContentStorer` y
`schemas/save-metadata.json` del tarball Lumi fijado. `step` no se trata como
restricción de múltiplos. El enforcer aplica tags/atributos HTML y puede truncar
por maxLength, incluso donde el checker genérico ignora ese atributo UI.

La preparación ejecuta ese enforcer sobre una copia y contrasta el JSON que
realmente se persistiría. Una diferencia produce LUMI_TRANSFORMATION_REQUIRED y
una lista transformations con path/before/after. No se modifica silenciosamente
el contenido original; el autor revisa y envía una corrección explícita. LaTeX
válido sobrevive al caso de sanitización probado. Las propiedades nombradas que
Lumi añade a ciertos arrays no forman parte del JSON persistido y no se reportan
como cambios de contenido. La incompletitud del enforcer upstream sigue siendo
un límite: no anunciamos seguridad HTML exhaustiva.

Idioma/licencia se contrastan con los patrones de Lumi y el idioma con Intl.Locale.
La expresión de H5P `^[-a-zA-Z]{1,10}$` no admite todo BCP 47: es-419 se rechaza
como incompatible, sin convertirlo automáticamente en es. Los códigos de licencia
se obtienen del esquema fijado, sin inventar equivalencia con identificadores SPDX.

## CI y alcance de cierre

El commit `fc2b687` pasó los cuatro jobs de wheel y los seis jobs Bun, incluyendo
TS7/Oxlint, publicación sin hardlinks y cancelación. El commit `08e0663` pasó el
workflow de wheel con la ampliación semántica y de medios. Las ejecuciones de
`060220c` incluyen además identidad de binario y navegador Linux. El workflow de
empaquetado/navegador y las seis combinaciones de identidad binaria ya pasaron.
Los últimos tests de cancelación real y la corrección del plazo total de llamada
MCP se verifican localmente y deben completar su propio CI.

Windows tiene evidencia local del corpus implementado. Linux/macOS pasaron
el corpus ampliado, procesos e identidad binaria de 060220c. Linux ARM64,
musl, proxy HTTPS configurado y Moodle gradebook no forman parte de este gate
local; no se anuncian como verificados. Bun no se promueve al MCP activo.

Los contratos F1 implementados se documentan en HARDENING.md: ZIP/extracción,
MIME, raíces, grafos, transformaciones, cancelación, publicación y límites.
Las raíces resueltas no eliminan TOCTOU frente a un proceso local hostil; los
snapshots inmutables y aislamiento remoto permanecen en F5/F6.

## Evidencia reproducible

Los comandos y probes son versionados. Los informes extensos quedan en exports:
b0-media.json, b0-media-bun-tree.json, b0-process.json, b0-hub.json,
b0-bun-identity.json, b0-browser-{node,bun}.jsonl y b0-grading-{node,bun}.jsonl.
Son evidencia de una ejecución, no rutas requeridas por el producto. El reporte
compacto versionado b0-f1-local-summary.json conserva estados y versiones.
