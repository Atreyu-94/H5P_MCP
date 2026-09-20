# 001 — Endurecimiento, migración TypeScript/Bun y servicio MCP H5P

## Estado y alcance

- Fecha: 2026-09-19. Revisión 10: F3 implementada y verificada localmente; CI multiplataforma pendiente. Siguiente: F4. Python y el MCP activo se conservan.
- Segunda fuente: [propuesta Bun](C:/Users/Vic/.codex/attachments/fb9aad3d-d4d0-4d62-8736-1df7b90267a4/Texto%20pegado.txt). No se instaló Bun ni se ejecutó B0 para editar este documento; la consulta de PATH no encontró bun.
- Repositorio: `D:\victorla\Documentos\School\Programming\IA\MCPs\H5P_MCP`.
- Base de la planificación inicial: `ac10c50`. La ejecución posterior usa main y pushes incrementales a Atreyu-94/H5P_MCP; consultar el informe de cierre local para commits y CI.
- Auditoría recibida: revisión de `1a7aa54d3daa0e0f3bdacf79bcc8f459be6e7bce`, anterior a los cinco commits de endurecimiento.
- Fuente: [auditoría adjunta](C:/Users/Vic/.codex/attachments/42395509-bfd6-49a1-a518-76b1a149268d/Texto%20pegado.txt).
- La preparación de este plan incluyó inspección de archivos y documentación. Las 57 pruebas del wheel y la prueba de puntuación True/False pertenecen a la ejecución anterior de esta tarea; no se repitieron durante esta planificación.

## Numeración y actualización del seguimiento

Los avances se comunican con el identificador de fase y tarea de este plan
(`F2`, `F2.5`, etc.) y su descripción. Los identificadores `Cxx` de la secuencia
de commits se conservan como referencias históricas de implementación; no
sustituyen la numeración de las tareas al informar el progreso.

Cada incremento implementado actualiza en el mismo commit el estado de las
tareas afectadas, el alcance realmente completado, las pruebas y lo pendiente.
Un commit posterior de seguimiento puede añadir el SHA definitivo y los enlaces
al CI cuando estén disponibles. Solo se marca `[x]` cuando se cumple el alcance
de la tarea; una entrega parcial mantiene `[ ]` y explica qué falta. El CI se
registra como pendiente, aprobado o fallido para su commit concreto, sin atribuir
a cambios nuevos los resultados de una revisión anterior.

## Objetivo

Migrar gradualmente a un monolito modular TypeScript con **Bun 1.4.2 como runtime y toolchain objetivo**, sujeto al gate B0, conservando autoría genérica, Lumi/Core 1.28, importación fresca, exportación autosuficiente y MathDisplay explícito. Primero alcanzar paridad local por stdio; después ofrecer un perfil remoto con identidades de objetos y autorización.

Bun sustituye a Node como dependencia de ejecución del producto final; Node queda como referencia temporal de CI, no como segundo runtime requerido por el usuario. El registro npm sigue siendo el canal de distribución, no el gestor canónico. No volver a generadores rígidos, microservicios, múltiples paquetes prematuros ni GitHub Actions como API. No asumir mejoras de rendimiento sin medirlas. Un proceso IPC persistente es una alternativa de transición, no una fase obligatoria.

La licencia de distribución, nombre/scope npm, proveedor OAuth, hosting y publicación requieren decisiones del propietario en sus gates respectivos. Preparar primero opciones y artefactos revisables. Aprobar el plan no equivale a publicar ni a modificar el MCP activo.

## 1. Diferencias entre auditoría y estado actual

| Recomendación | Estado local inspeccionado | Trabajo restante |
|---|---|---|
| regexp, decimals, maxLength HTML | Implementados en semantics.cjs | Pruebas diferenciales y atributos restantes |
| Profundidad, nodos, UUID | Límites Python/Node y UUID validados | Revisar todos los recorridos/grafos y conservar identidad |
| Medios, JSON, procesos, lotes | Límites configurables y medios secuenciales | MIME real, cuotas, cancelación efectiva |
| Seguridad ZIP | Duplicados literales, traversal, tamaños declarados y JSON acotado | Comprimido, ratio, symlinks, colisiones normalizadas y extracción real |
| Preparación | Manifiesto SHA-256, parches, backend, medios y STALE_PREPARATION | Snapshot inmutable y preparation_id persistente |
| Respuestas | TypedDict y estados passed/failed/not_run | Completar esquemas, códigos y detalles en toda la cadena |
| CI | Workflow Windows/Linux, Python 3.12/3.13, Node 22.12 | Ejecutar en GitHub; ampliar matriz, tipos/lint y navegador |
| Caché personal | Fixture de 23 bibliotecas con checksum; aislamiento por defecto | Lock de producción distinto del de tests |
| Bytecode | Retirado del índice | Guardia contra reintroducción |
| H5P históricos | Siguen versionados bajo h5p_mcp/exports | Inventario y retirada del índice preservando archivos útiles |
| package_validator | Ya existe; quiz_validator es shim | Mantener compatibilidad durante transición |
| Separación de módulos | media.cjs y reglas escalares separadas | Completar separación en TypeScript |
| Administración | refresh/install todavía son flags; anotaciones ya no prometen lectura pura | Separar herramientas y permisos |
| Publicación | os.link exclusivo | Fallback portable sin sobrescritura ni parciales |
| Licencias | Raíz Apache-2.0; Lumi declara GPL-3.0-or-later | Decisión documentada antes de npm/OCI públicos |
| HTTP/tenants/Tasks/OCI/Registry | Ausentes | Implementaciones nuevas, condicionadas por seguridad |

### Invariantes que deben preservarse

- [ ] Versiones exactas Name major.minor, sin sustitución silenciosa.
- [ ] Lumi sigue empaquetando/importando; no escribir ZIP de actividades manualmente.
- [ ] Validación de importación en almacenamiento vacío y temporal único.
- [ ] Publicación completa, exclusiva y sin sobrescritura, incluso con concurrencia.
- [ ] Dependencias explícitas; MathDisplay sin duplicados ni filtración a contenido sin fórmulas.
- [ ] Defaults, grupos aplanados, subcontenidos y medios conservan semántica H5P.
- [ ] UUID válidos se conservan al preparar/exportar; duplicados se rechazan.
- [ ] Descargas y mutaciones del Hub explícitas.
- [ ] Importación no implica reproducción, accesibilidad o calificaciones Moodle.
- [ ] Skills conserva recursos permitidos, digests, tamaños y compatibilidad de clientes.

## 2. Decisiones y ajustes a las recomendaciones

### Arquitectura y concurrencia

Un paquete TypeScript con domain, application, h5p, infrastructure y adapters. Python utiliza un adaptador IPC del mismo núcleo durante la transición. No mantener dos implementaciones independientes del validador indefinidamente. Empezar con trabajos aislados; introducir IPC persistente únicamente si reduce riesgo o mejora una necesidad medida.

El proceso MCP Bun persiste durante la sesión y llama directamente al adaptador Lumi en el camino ordinario; no inicia Python/Node en cada tool call. Mantener el dominio TypeScript libre de Bun.*, limitado a infraestructura/transporte. Cargar inicialmente Lumi CJS con createRequire sin reescribirlo ni cambiar su versión. Compartir catálogo/esquemas por generación inmutable, no una instancia mutable de H5PEditor sin pruebas. Administración exclusiva; exportación/importación en pool acotado con temporales propios. Conservar procesos Bun aislados para operaciones no confiables o que requieran terminación dura; una cola asíncrona no interrumpe CPU síncrona. Evitar worker_threads inicialmente. Un mutex en memoria solo coordina un proceso: dos clientes locales con almacén común requieren coordinación entre procesos; varias réplicas requieren snapshots inmutables y coordinación persistente/distribuida.

### Runtime y extensiones

Bun **1.4.2 exacto** es el candidato canónico: fijarlo en `.bun-version`, `packageManager`, CI e imagen por digest. Promoverlo después de B0, sin cambiar hoy el runtime activo. Bun es runtime, gestor, ejecutor, bundler y runner de unitarias; `bun.lock` será la única autoridad del producto tras la comparación del árbol instalado.

TypeScript 7 es el comprobador estático objetivo, fijando su parche y ejecutable local exactos en B0. Bun transpila, pero no sustituye el typecheck. Verificar compatibilidad de lint con la API nativa de TS7: si requiere API TS6, usar adaptación de tooling documentada, sin bajar silenciosamente el compilador principal. `bun:test`, conformance y navegador son suites distintas; Node mantiene un runner propio para el corpus diferencial, porque `bun:test` no corre bajo Node.

Node 24 LTS y 22.12 permanecen como referencias fijadas durante transición. Tras F4-R, conservar el harness diferencial al menos dos releases estables y retirarlo mediante decisión con evidencia. No hacer Node 26 ni musl/Alpine requisitos iniciales. Matriz Bun bloqueante: Linux x64 glibc, Windows x64 y macOS arm64. Linux arm64 se certifica antes de ofrecer esa imagen; runner ausente significa no verificado, nunca aprobado.

La documentación oficial consultada confirma SDK TypeScript v2 estable y MCP 2026-07-28. Tasks sigue siendo una extensión separada: realizar spike de SDK, negociación y cliente. El rango engines.bun no será una promesa de futuras versiones: producción usa 1.4.2 exacto hasta certificar una actualización; no ampliar automáticamente a toda la rama 1.4.

### Identidades y preparación

Preservar UUID existentes. No aplicar UUIDv5 basado solo en JSON Pointer: reordenar preguntas podría cambiar identidad y seguimiento. Evaluar UUIDv5 únicamente como modalidad explícita con namespace estable y reglas de clonación. Paridad exige estabilidad, no determinismo universal.

Primera implementación: preparation store con TTL, propietario, snapshot de bibliotecas y copia de medios. Editar crea una preparación nueva. Un token firmado sin storage no conserva bytes ni resuelve retención/revocación: alternativa futura, no requisito inicial.

### Contratos y verificación

semantics.json sigue siendo autoridad. JSON Schema describe la envoltura y una proyección comprobada, sin simular equivalencia completa con widgets. Los params siguen siendo dinámicos por biblioteca.

Importación, reproducción, grading y accesibilidad son checks independientes. Una etiqueta resumida del catálogo debe acompañarse de versiones, digests, fecha, evidencia y comprobaciones pendientes; no tratar accesibilidad como prueba de grading.

### Licencias

Inventariar código propio, Lumi y bibliotecas H5P, fuente correspondiente, cambios y avisos. Preparar opciones y obtener decisión del titular con revisión especializada cuando proceda. No relicenciar contribuciones ajenas ni asumir que un subproceso elimina obligaciones. Este gate bloquea nuevas distribuciones públicas npm/OCI, no las pruebas locales.

### Contraste documental de la propuesta Bun (2026-09-19)

| Afirmación | Resultado del contraste | Consecuencia |
|---|---|---|
| Bun 1.4 migró de Zig a Rust y mejoró compatibilidad | Confirmado en el anuncio oficial; compatibilidad sigue incompleta | Motiva B0, no demuestra rendimiento de H5P |
| Bun 1.4.2 disponible | Confirmado en release oficial del 5 de septiembre | Candidato exacto; no seguir latest automáticamente |
| SDK MCP v2 admite Bun y Hono | README oficial declara Bun y middleware @modelcontextprotocol/hono | No hace falta protocolo artesanal; probar transporte real |
| TypeScript 7 nativo en Go | Confirmado por Microsoft | Typecheck separado, compatibilidad lint/API requiere revisión |
| crc32 N-API es dependencia real | package-lock local fija @node-rs/crc32 1.10.8 vía yauzl-promise | Test real de carga y CRC por SO/arquitectura |
| Lumi está certificado para Bun | No demostrado por la propuesta ni por pruebas locales | B0 obligatorio; engines Node no prueba incompatibilidad ni soporte Bun |
| bunx implica Bun | No: respeta shebang; --bun fuerza runtime | Inspeccionar proceso efectivo y bin distribuido |
| Basta B0 para eliminar Python | No: B0 solo certifica motor/dependencias | Retirada después de F4 y R.1–R.7 |
| Mutex local reemplaza todo FileLock | Solo si hay un único proceso escritor | Conservar coordinación multiproceso/generaciones |
| Proceso persistente elimina necesidad de aislamiento | No para entradas no confiables o CPU no abortable | Cola limitada más procesos Bun cuando sean necesarios |

Fuentes de esta revisión:

- [Bun 1.4](https://bun.com/blog/bun-v1.4): anuncio y límites de compatibilidad; sus porcentajes y benchmarks son del proveedor, no mediciones del repositorio.
- [Bun 1.4.2](https://bun.com/blog/bun-v1.4.2): versión publicada y correcciones; no extrapolar a estabilidad certificada de Lumi.
- [Node-API en Bun](https://bun.com/docs/runtime/node-api): compatibilidad no absoluta, razón para certificar el addon nativo.
- [SDK MCP oficial](https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md): Bun, stdio y adaptador Hono.
- [TypeScript 7](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/): compilador nativo y limitaciones de transición de tooling.
- [TypeScript en Bun](https://bun.com/docs/typescript): ejecución/transpilación separadas de comprobación de tipos.
- [Lockfile Bun](https://bun.com/docs/pm/lockfile) y [linker](https://bun.com/docs/pm/isolated-installs): migración de dependencias y selección hoisted durante compatibilidad.
- [bunx](https://bun.com/docs/pm/bunx): shebang y --bun.
- [bun pm pack](https://bun.com/docs/pm/cli/pm): tarball para registro npm y control de scripts de empaquetado.
- [Ejecutables Bun](https://bun.com/docs/bundler/executables): posibilidad técnica; no sustituye prueba en plataforma destino.

### Toolchain propuesta, todavía sin ejecutar

Usar packageManager bun@1.4.2 y .bun-version coherentes; al fijar TS7/SDK/@types/bun registrar versión exacta e integridad. Empezar con linker hoisted. Toda instalación usa --ignore-scripts; una dependencia que requiera scripts necesita diagnóstico y excepción acotada, no habilitación global. Auditar también hooks prepare/prepack al distribuir.

Comandos de referencia PowerShell para el paquete futuro, una vez definidos los scripts:

```powershell
bun --version
bun install --frozen-lockfile --ignore-scripts
bun run typecheck
bun test
bun run build
bun pm pack --ignore-scripts
```

`typecheck` invoca el tsc local fijado con --noEmit; nunca descarga una versión latest al ejecutar CI. `build` produce dist para Bun y recursos externos verificables. `bun --watch src/cli.ts stdio` se limita al desarrollo, no al comando MCP de producción. El tipo de esquema (por ejemplo Zod v4 o Ajv) se decide tras comprobar integración SDK y contrato, evitando validar dos veces con semánticas divergentes.

## 3. Secuencia y dependencias

| Fase | Prioridad | Dependencias | Gate |
|---|---|---|---|
| F0 Baseline y decisiones | P0 | Ninguna | Inventario, ADR y medición repetible |
| B0 Certificación Bun sin reescritura | P0 | F0 | Lumi/N-API/ZIP y árbol de dependencias certificados |
| F1 Robustez local y CI | P0 | F0; B0 para adoptar Bun | Fronteras de archivos/procesos y suite verificadas |
| F2 Contratos vNext | P0 para remoto | F0/F1 | Permisos separados, esquemas y compatibilidad |
| F3 Núcleo TypeScript/Bun | P1 | B0/F1/F2 | Paridad semántica e aislamiento |
| F4 MCP Bun stdio | P1 | F3 | Tarball Bun, Skills, clientes y conformidad |
| F4-R Retirada de Python | P1 | F4 y paridad de seguridad F1 | Runtime Bun independiente; release previa recuperable |
| F5 Stores y snapshots | P0 para remoto | F2/F3 | Inmutabilidad, ownership e idempotencia |
| F6 HTTP protegido | P0 para remoto | F4/F5 | OAuth, cuotas, cancelación y aislamiento |
| F7 Distribución | P1 | F4 para npm; F6 para remoto | Licencias, artefactos y publicación autorizada |
| F8 Evaluación IA/Moodle | Transversal | Baseline F0 | Evidencia comparable por check y entorno |
| F9 Binario autónomo opcional | P2 | F7 estable | N-API, recursos y binario por plataforma certificados |

B0 precede a la migración de runtime, no a todas las correcciones locales F1. Si B0 falla, continuar seguridad/documentación pero no promover Bun ni retirar Python. Correspondencia con la propuesta: B1→F3, B2→F4, B3→F4-R, B4→F6, B5→F9. F5 puede diseñarse mientras se completa F4. No exponer HTTP antes de cerrar F5. F8 empieza con el sistema actual y se repite en cada gate. Cada fase produce commits integrables y reversibles, sin cambiar varias interfaces a la vez.

## 4. F0 — Baseline, inventario y decisiones

**Archivos:** HARDENING.md, pyproject.toml, lumi/provenance.json, tests/fixtures; nuevos docs/architecture y tests/benchmarks.

- [x] F0.1 Registrar HEAD/árbol/remoto, checksums del backend y fixtures; preservar cambios ajenos.
- [x] F0.2 Reproducir unitarias offline, integración aislada, wheel externo y navegador. Archivar logs estructurados con commit, SO, runtime, versiones y resultados. Evidencia en docs/architecture; pytest conserva resumen transcrito, no log bruto.
- [x] F0.3 Inventariar H5P históricos y consumidores de html_utils/zip_utils. Retirar solo archivos confirmados del árbol activo; no reescribir historial Git ni borrar material local del usuario.
- [x] F0.4 ADR de licencias: comprobar contenido real del tgz, fuentes/parches, componentes y obligaciones; registrar responsable y condición de desbloqueo. Inventario generado; la autorización de distribución sigue pendiente para F7.
- [x] F0.5 Fijar SDK v2 y conformidad por versión/commit; comprobar APIs reales de Skills/Tasks y toolchain Bun 1.4.2/TypeScript 7 y Node 22/24 de referencia. Tarball SDK verificado y Skills probado por stdio; tipos Tasks inspeccionados, su ciclo de vida permanece not_run para F4/F6; runtimes candidatos no certificados hasta B0.
- [x] F0.6 Línea base A (Python+Node por petición): catálogo, esquema, preparación, exportación, importación y lotes; mediana/p95, RSS muestreado del árbol, bytes, handles y adquisición del lock. 20 repeticiones de operaciones cortas y 5 exports/imports. Instalación con caché npm inicialmente vacía y nueva instalación offline con caché reutilizada verificadas; runtime ya instalado y primera llamada separados. Lotes 10/100 medidos, 100 rechazado por defecto y permitido solo mediante override aislado. Evidencia en baseline-a-instrumented.json y baseline-installation.json. Caché física del SO no vaciada: no se certifica arranque frío del SO. Comparación B/C pendiente en F3.8, no marcada como ejecutada.
- [x] F0.7 Proponer ventana de compatibilidad Python y nombre npm sin publicarlo. Revisar existencia de Release Please antes de configurar releases.

**Aceptación:** resultados reproducibles y decisiones pendientes explícitas. No sustituir fallos actuales por reportes históricos. Moodle no bloquea baseline local; sus checks quedan not_run.

## 4B. B0 — Certificar Bun antes de reescribir o cambiar runtime

**Entrada:** HEAD de la implementación endurecida, bridge CJS sin cambios funcionales, tarball Lumi efcfeebc y fixtures bloqueadas. La comparación no debe usar únicamente el commit antiguo 1a7aa54.

**Avance 2026-09-19:** subconjunto local de B0.1–B0.7 ejecutado con resultados documentados; corpus ampliado con PNG, STALE_PREPARATION, MathDisplay ausente y paquete incompleto. Matriz y gates restantes pendientes. El workflow preparado solo prueba el subconjunto, no certifica B0 completo. El hallazgo de red implícita de discover fue corregido en 641a60e; las regresiones y suite de 60 pruebas pasan. El MCP activo no se ha actualizado.

**Archivos nuevos previstos:** `.bun-version`, configuración de instalación aislada bajo `tests/runtime-compat/`, `bun.lock` junto a su package.json, harness diferencial, fixtures multimedia autorizadas y workflow de compatibilidad. Mantener intacto el package-lock del producto Python mientras setup_lumi lo consuma.

- [x] B0.1 Fijar Bun 1.4.2 y setup-bun por SHA; verificar versión efectiva/checksum por plataforma. Registrar SO, arquitectura, libc y CPU. No usar latest ni auto-upgrade.
- [x] B0.2 Comparación de runtime controlada: crear árbol npm de referencia en temporal, scripts deshabilitados, e invocar el mismo bridge con Node y Bun sobre copias idénticas de bibliotecas. Cambiar solo el ejecutable en el harness, sin tocar la configuración activa del usuario.
- [x] B0.3 Comparación de instalador separada: migrar package-lock→bun.lock en el directorio experimental, linker hoisted, instalar con `bun install --frozen-lockfile --ignore-scripts`. Comparar versiones, integrities, tarball Lumi y binarios opcionales seleccionados. No cambiar gestor y runtime a la vez sin distinguir sus diferencias.
- [x] B0.4 Probar carga efectiva de @node-rs/crc32 1.10.8 y vectores CRC32 conocidos, no solo resolución del paquete. Confirmar qué binario .node se carga. Preservar optionalDependencies por plataforma; no habilitar scripts globalmente si falla. Revisión explícita de cualquier excepción.
- [x] B0.5 Ejecutar catalog, discover cacheado, schema, prepare, export e importación vacía con TF/MC/Blanks/QuestionSet/Accordion, imágenes/audio/vídeo válidos, anidados, assets locales y MathDisplay presente/ausente. Incluir entrada inválida, IDs, presupuestos, no-overwrite, STALE_PREPARATION y paquete incompleto.
- [x] B0.6 Comparar h5p.json, content/content.json, mainLibrary, dependencias/parches, archivos de biblioteca, hashes de medios y diagnósticos. Dar los mismos UUID en fixtures de paridad; la generación de UUID ausentes se prueba como propiedad independiente para evitar falsos diffs aleatorios.
- [x] B0.7 Importar paquetes de ambos runtimes en almacenamiento vacío, incluyendo cruce Node→Bun/Bun→Node. Reproducir en navegador y comprobar scores/feedback matemático. No exigir bytes ZIP idénticos por timestamps u orden.
- [x] B0.8 Probar EOF/stdin/stdout/stderr, errores de streams, backpressure, handles, temporales, señales y kill del hijo en Windows/Linux/macOS. Repetir operaciones para detectar crecimiento retenido; registrar métricas de memoria sin atribuir todo RSS al heap JS.
- [x] B0.9 Pruebas de red separadas y explícitas: refresh Hub e instalación en almacén descartable, TLS y proxy HTTPS si se anuncia soporte. Corpus offline bloqueante sin Hub; fallo de red externa no se confunde con incompatibilidad, pero funcionalidad no probada queda pendiente de certificación.
- [x] B0.10 Matriz obligatoria Bun 1.4.2: Ubuntu x64 glibc, Windows x64, macOS arm64, comparadas con Node fijado. Linux arm64 como gate de esa distribución. Musl/Alpine y worker_threads no forman parte del soporte inicial.
- [x] B0.11 TypeScript 7.0.2 y @types/bun 1.4.2 verificados con Oxlint 1.83.0/tsgolint 7.0.2002; sin ESLint ni TS6. strict, noUncheckedIndexedAccess y noImplicitOverride; dominio sin globales Bun, adaptadores con Bun; ES2022 y skipLibCheck=false. Casos positivo/negativo ejecutados con Node y Bun. Evidencia en docs/architecture/002-bun-compatibility.md.
- [x] B0.12 Emitir reporte máquina/Markdown con checks passed/failed/not_run y decisión adoptable/bloqueado por plataforma. Marcar Bun predeterminado solo en el componente que haya superado su gate; una prueba del bridge no certifica todavía el nuevo MCP.

**Gate B0:** corpus actual y nuevos casos sin diferencias semánticas no explicadas; N-API funciona; importación fresca y navegador pasan; no fuga de handles/temporales/stdout. Si falla, guardar reproducción y conservar producción Python/Node. No adaptar fixtures para ocultar diferencias. La hipótesis de viabilidad no equivale a certificación.

**Contraste de la propuesta:** no existe compilación JS por petición: el bridge CJS se ejecuta directamente. La mejora arquitectónica esperada es retirar la envoltura y el arranque por llamada; el beneficio adicional de Bun debe aislarse mediante benchmark A/B/C. La migración a Rust y las mejoras de compatibilidad publicadas por Bun no permiten inferir por sí solas rendimiento o estabilidad de H5P.

## 5. F1 — Robustez local y CI

**Archivos:** lumi_backend.py, limits.py, lumi/{limits,media,semantics,manifest}.cjs, validators/package_validator.py, exporters/h5p_exporter.py, tests y workflows.

- [x] F1.1 Limitar tamaño comprimido antes de abrir ZIP; ratio, bytes reales descomprimidos por entrada/total, profundidad de rutas y dependencias. Fijar umbrales con fixtures; ratio nunca sustituye límite absoluto.
- [x] F1.2 Rechazar symlinks por atributos ZIP, rutas UNC/unidades/ADS, traversal, separadores ambiguos y colisiones normalizadas/case-folding. Probar nombres reservados Windows. Permitir carpetas H5P legítimas; no extraer ZIP internos recursivamente. Implementado en prevalidación; aplicación a administración/extracción permanece en F1.3. Evidencia en docs/architecture/003-local-hardening.md.
- [x] F1.3 Aplicar prevalidación también a instalación administrativa. Comprobar límites durante extracción en worker aislado, no solo en directorio central.
- [x] F1.4 Detectar MIME real frente al declarado, allowlist de formatos y política SVG/contenido activo. Conservar validaciones de Lumi, sin asumir que cubren todo.
- [x] F1.5 Configurar raíces autorizadas para medios, lectura de paquetes y destinos locales. Migración explícita de usuarios de rutas absolutas; resolver symlinks y revisar acceso al abrir, documentando TOCTOU.
- [x] F1.6 Acotar grafos con nodos/aristas/profundidad y detectar ciclos; cubrir recorridos de defaults, esquemas, MathDisplay y manifiestos.
- [x] F1.7 Contrastar step, HTML/tags, BCP 47 y códigos de licencia con H5P/Lumi fijados. Separar restricciones reales de atributos UI. Sanitización compatible sin alterar respuestas/LaTeX silenciosamente; reportar transformaciones materiales.
- [x] F1.8 Deadline que incluya espera de cola/lock; cancelación con terminación y reap del worker. Probar durante lectura, importación y escritura, sin artefacto final parcial.
- [x] F1.9 Fallback sin hardlinks: staging y primitiva no-replace o artifact store transaccional. Nunca copia directa al nombre final ni rename con overwrite. Error explícito si el filesystem no permite garantizarlo.
- [x] F1.10 CI Bun 1.4.2 en Windows x64/Linux x64 glibc/macOS arm64, Node 22.12/24 diferencial, Python 3.12 transitorio y 3.13 compatible; lint/tipos/unitarias/importación/wheel externo/stdio. Acciones fijadas por SHA, permisos mínimos, sin secretos para PR no confiable.
- [x] F1.11 Navegador portable con Core/Playwright fijados, sin rutas Temp personales. Acierto/error/reintento/finalización y dos ramas de feedback matemático. Conformidad solo de transportes implementados.
- [x] F1.12 Guardia contra artefactos versionados con allowlist de fixtures legítimas; retirar H5P históricos del índice tras inventario. No eliminar fixtures/tgz trazables con reglas indiscriminadas.

**Aceptación:** casos debajo/en/encima del límite, ZIP bomb/traversal/symlink/MIME falso rechazados controladamente, cancelación limpia, dos escritores sin overwrite. CI ejecutado, no solo YAML creado. Vulnerabilidades de dependencias requieren triage explícito.

## 6. F2 — Contratos para agentes y administración

**Archivos:** nuevos contracts/, server.py, models/, skills_extension.py y tests/contracts/.

| Actual | vNext | Transición |
|---|---|---|
| list_h5p_activities | search_h5p_types | Alias local deprecado |
| get_h5p_activity_schema | get_h5p_type_contract | Recurso bruto adicional; sin instalación implícita |
| create_h5p_activity | prepare_h5p_activity | Preparación identificada; compatibilidad del objeto local |
| export_h5p | export_h5p_activity | preparation_id; legado solo local |
| validate_h5p | validate_h5p_package | Ruta local autorizada o package_id remoto, esquemas distintos |
| export_h5p_batch | export_h5p_batch | Forma local acotada; tareas negociadas después |
| refresh/install flags | Herramientas administrativas | Fuera del catálogo remoto ordinario |

- [x] F2.1 JSON Schema de entrada/salida, propiedades cerradas donde corresponda y params dinámicos. Autoridad contractual compartida Python/TS; snapshots JSON.
- [x] F2.2 Diagnósticos: code, JSON Pointer, message, expected/actual acotados, retryable y suggested_fix. No devolver secretos ni material completo. Distinguir reintento transitorio de reparación del input.
- [x] F2.3 Mapping versionado de códigos actuales a LIBRARY_NOT_INSTALLED, LIBRARY_VERSION_MISMATCH, SCHEMA_VALIDATION_FAILED, UNSUPPORTED_SEMANTIC_TYPE, STALE_PREPARATION, ASSET_NOT_FOUND, ASSET_TOO_LARGE, MIME_MISMATCH, UNSAFE_ARCHIVE, OUTPUT_ALREADY_EXISTS, HUB_UNAVAILABLE y TARGET_INCOMPATIBLE.
- [x] F2.4 Validación negativa retorna informe; fallo operativo usa isError y conserva detalles. Mapear excepciones Python, Node, batch y transporte consistentemente.
- [x] F2.5 Consultas puras; separar refresh_h5p_catalog, install_h5p_library e install_h5p_library_package. Scopes al listar e invocar; imagen inmutable deshabilita administración. Anotaciones completas coherentes con efectos, nunca usadas como autorización. Implementada en bbf8c7e para el perfil local y el bloqueo por H5P_MCP_IMMUTABLE; la imagen OCI y OAuth corresponden a F6/F7. Ver docs/architecture/005-f2-contracts.md.
- [x] F2.6 Contrato compacto con requeridos/defaults/tipos/restricciones/subbibliotecas y ejemplos probados. Recurso bruto por URI/digest; x-h5p documenta widgets y límites. Diferencial contra semántica fuente. get_h5p_type_contract conserva reglas nativas y grupos de un campo; ejemplos de TrueFalse sujetos a patch y SHA-256, sin evidencia de Moodle. Recursos acotados al proceso, no stores persistentes de F5.
- [x] F2.7 Catálogo con structurally_authorable y checks/versión/digest/fecha/evidencia; compatibilidad temporal del booleano anterior sin atribuirle pruebas inexistentes.
- [x] F2.8 Export retorna resource link, MIME, tamaño, SHA-256 y manifest, nunca paquete base64 en respuesta. Recuperación de recursos acotada.
- [x] F2.9 Esquemas local/remoto separados: remoto no tiene path para medios, validación, recursos ni administración. Esquemas publicados y probados; ejecución remota deshabilitada hasta F5/F6.

### Trazabilidad de F2

Las filas «Cierre F2» corresponden al commit `9c88322`
(`feat(contracts): complete F2 operations and artifact resources`).

| Tarea | Estado y alcance implementado | Commits | Verificación y pendiente |
|---|---|---|---|
| F2.1 | Completa: autoridad JSON compartida y validación de entradas/salidas de todas las operaciones vNext locales. | `0e2093c`, `9ad543b` + cierre F2 | Esquemas resueltos publicados por recurso; parámetros H5P permanecen dinámicos. |
| F2.2 | Completa: diagnósticos públicos acotados para preparación, consultas, administración, exportación, validación y batch. | Cierre F2 | Pruebas de punteros, límites, datos sensibles y errores operativos. |
| F2.3 | Completa: mapping versionado aplicado a las nuevas interfaces, con PERMISSION_DENIED adicional. | Cierre F2 | ZIP inseguro, archivo ausente, colisión, fallos del backend y rechazo administrativo. |
| F2.4 | Completa: informes negativos frente a isError operativo, también por elemento del lote; aliases legados conservados. | Cierre F2 | Cliente MCP real, stdio, importación real y fallos simulados. |
| F2.5 | Completada para el perfil local: herramientas administrativas separadas, scopes al listar/invocar, modo inmutable y consultas sin mutación de bibliotecas/caché. | `bbf8c7e` | 128 pruebas completas y 30 desde wheel externo; build, Oxlint y validación de skill aprobados. OAuth e imagen OCI se verifican en F6/F7. |
| F2.6 | Implementada: proyección nativa, campos/defaults/restricciones/subbibliotecas, notas x-h5p y recurso canónico acotado con URI/SHA-256. Dos ejemplos TrueFalse probados; otros tipos devuelven ejemplos vacíos. | `21d3284` | 135 pruebas completas y 10 desde wheel externo aprobadas. Diferencial sobre los 9 archivos de semánticas, preparación de ejemplos y restricciones, integridad/evicción/límites, lectura MCP y ausencia de mutación. CI del nuevo incremento pendiente. |
| F2.7 | Completa: evidencia por versión/patch, digest, fecha, checks y structurally_authorable. Booleano anterior es alias. | Cierre F2 | Preparación, importación, reproducción y grading permanecen not_run en evidencia del catálogo. |
| F2.8 | Completa: export_h5p_activity devuelve ResourceLink, MIME, tamaño, SHA-256 y manifest; lectura por ID con límite e integridad. | Cierre F2 | Exportación y lectura real; cambios de bytes, ID desconocido y exceso de tamaño rechazados. IDs locales acotados al proceso. |
| F2.9 | Completa: perfiles publicados local/remoto, entradas remotas cerradas basadas en IDs. | Cierre F2 | Rechazo de rutas en campos de entrada remotos. Persistencia/ownership y transporte corresponden a F5/F6. |

CI aprobado de `9ad543b` para la entrega parcial F2.1–F2.4:
[paquete y navegador](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35488159953),
[matriz Bun/Node](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35488160084).

CI de `bbf8c7e` para F2.5, al actualizar esta revisión:
[paquete y navegador aprobado](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35488764390);
[matriz Bun/Node aprobada](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35488764477).

Verificación del cierre F2: 139 pruebas aprobadas desde el wheel instalado fuera del checkout en Windows, con dependencias fijadas, en 154,85 s. Build, Oxlint, skill y guardia de artefactos aprobados. CI del cierre pendiente; no se atribuyen a este cambio los resultados previos. El CI de F2.6 (`5c3726f`) terminó aprobado: [paquete](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35489543309) y [Bun/Node](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35489543275).

**Aceptación:** consultas ordinarias sin mutación/red oculta; administración directa sin scope falla; clientes legados funcionan en modo local; errores permiten reparar campos concretos.

## 7. F3 — Núcleo TypeScript por paridad

**Árbol previsto:** src/domain, src/application, src/h5p, src/infrastructure, src/adapters y src/skills, en un solo paquete. Bun.* solo en infraestructura/adaptadores; casos de uso y validadores siguen comparables con Node. Crear módulos cuando exista responsabilidad real.

- [x] F3.1 TypeScript 7 strict, bun.lock, Oxlint y bun:test; Python conservado.
- [x] F3.2 Tipos, límites, diagnósticos, reglas, UUID, MathDisplay, medios, manifiesto y grafo portados.
- [x] F3.3 Operaciones Lumi separadas, con el mismo upstream fijado.
- [x] F3.4 Caché de semánticas/regexps por digest, generación y compilador; límites e invalidación probados.
- [x] F3.5 Pool, staging y generaciones privadas inmutables; publicación exclusiva. Se conserva el lock legado.
- [x] F3.6 IPC Python correlacionado, acotado y cancelable; trabajos sensibles en procesos aislados.
- [x] F3.7 Paridad A/B/C: 9 fixtures y 9 proyecciones; JSON, dependencias, medios, UUID y diagnósticos.
- [x] F3.8 Instalación vacía/cacheada, primeras llamadas, 20 muestras cortas y lotes 10/100 medidos. Regresiones documentadas; caché física del SO no vaciada.

Commit: `f47fb7b`. Validación: 139 pruebas del wheel, 6 del núcleo/IPC y navegador aprobados. Evidencia y límites: docs/architecture/006-typescript-core.md y f3-local-summary.json. CI pendiente; comparador de fechas de F2 corregido en `eeb44aa`.

**Aceptación:** corpus positivo/negativo equivalente o diferencias aprobadas/documentadas; importación fresca y navegador conservan comportamiento; rollback al runtime Python disponible.

## 8. F4 — MCP Bun stdio, CLI y Skills

- [ ] F4.1 SDK oficial v2 sobre los casos de uso en proceso Bun persistente; stdout solo protocolo, logs stderr, negociación y cierre limpio.
- [ ] F4.2 CLI stdio, validate, export y administración local; HTTP se habilita en F6.
- [ ] F4.3 Migrar Skills con digest/tamaño/URI allowlist. Verificar estructura real de SEP-2640: no asumir que cada archivo de referencia debe publicarse como una skill separada en skills/list.
- [ ] F4.4 SKILL.md breve y referencias workflow, selecting-content-types, native-semantics, media, mathematics, moodle-handoff, validation-errors y security. Ejemplos TF/MC/Accordion/QuestionSet validados. Cada recurso adicional registrado y autorizado, nunca ruta arbitraria.
- [ ] F4.5 Conformidad oficial fijada por commit/versión; escenarios stdio, cliente con Skills y cliente sin extensión, fallback explícito.
- [ ] F4.6 Empaquetar con bun pm pack --ignore-scripts después del build e instalar tarball externo sin checkout/caché, con dist, Skills, notices y dependencias Lumi/N-API completas. Probar bunx --bun <paquete>@<version> stdio y shebang #!/usr/bin/env bun en tres SO; comprobar proceso efectivo con Node/Python ausentes del entorno de ejecución. El paquete/versión concretos se deciden en F0, no copiar h5p-mcp@0.2.0 como identidad disponible.
- [ ] F4.7 Documentar uvx→bunx y transición hacia la última release Python congelada; F4-R decide la retirada tras paridad. No modificar ni desinstalar el MCP activo automáticamente.

**Aceptación:** paridad funcional y de protocolo, recursos/Skills correctos, tarball instalable y sin procesos huérfanos. Retirar Python solo tras gate y transición acordada.

## 8R. F4-R — Retirada verificable de Python y del runtime Node de producción

**No ejecutar al cerrar únicamente B0.** La frase de la propuesta que liga la retirada a B0 se sustituye por el gate completo de F4: B0 demuestra el motor, no las herramientas, Skills, seguridad ni el empaquetado del servidor nuevo.

- [ ] R.1 Tabla de paridad de cada responsabilidad Python: modelos, ZIP, rutas, publicaciones, locks, errores, cancelación, CLI, MCP y Skills. Todas deben tener implementación y tests Bun antes de borrar el original.
- [ ] R.2 Resolver disponibilidad del tarball Lumi al instalar el paquete distribuido: no dejar un file: relativo a un checkout inexistente. Usar dependencia trazable compatible con la decisión de licencias o contenido vendorizado completo, manteniendo hash y fuente.
- [ ] R.3 Validar dist con Bun. Mantener Lumi/N-API externos al bundle inicial si la resolución dinámica lo requiere; verificar que están en el artefacto instalable. Bun build no incluye automáticamente archivos .node, Skills ni bibliotecas dinámicas.
- [ ] R.4 Entorno limpio con Bun y sin Python/Node para ejecución stdio/CLI: descubrir→preparar→exportar→validar, Skills y cierre/cancelación. Herramientas auxiliares de CI pueden requerir Node, pero el producto instalado no.
- [ ] R.5 Retirar FastMCP/Pydantic, lumi_backend, puente IPC y ficheros Python de producto en commit separado; portar primero las pruebas a bun:test y mantener la release Python congelada como rollback. No borrar datos ni bibliotecas del usuario.
- [ ] R.6 Promover bun.lock como única autoridad de dependencias de producto. Conservar package-lock antiguo solo en fixture/harness legado identificado si el oráculo aún lo necesita; no dos gestores actualizando la misma raíz. Documentar uvx→bunx sin editar el cliente activo.
- [ ] R.7 Conservar corpus Node diferencial durante al menos dos releases estables Bun; después retirar el harness mediante reporte de estabilidad y decisión explícita. Eliminarlo no implica borrar evidencia histórica.

**Aceptación:** cero invocaciones Python/Node en el camino normal observado, tarball íntegro, interfaz MCP equivalente y rollback documentado. La publicación pública sigue condicionada a licencias F7 aunque la retirada del código ya esté lista.

## 9. F5 — Stores, snapshots e idempotencia

- [ ] F5.1 asset_id, package_id, preparation_id y artifact_id opacos con owner/tenant/TTL. Los IDs no son credenciales: autorización por objeto en cada acceso.
- [ ] F5.2 Upload en staging con límites incrementales, firma/MIME, hash y nombre interno asignado por servidor; publicar únicamente tras validar.
- [ ] F5.3 Preparaciones inmutables con parámetros normalizados, medios copiados y library_snapshot_id. Expiración/ausencia/integridad producen diagnóstico específico.
- [ ] F5.4 Idempotency key ligada a tenant y digest: misma clave/input reutiliza resultado; input diferente produce conflicto. Probar carrera y caída entre escritura y registro.
- [ ] F5.5 Artifact store con publicación transaccional, hash/tamaño/MIME, retención, huérfanos y borrado autorizado. URLs firmadas breves o descarga autenticada; expiración y revocación probadas.
- [ ] F5.6 libraries.lock de producción con máquina/major/minor/patch, hashes, fuente y evidencia; no confundirlo con lock ZIP de tests. Administración crea generación nueva; rollback de generación.
- [ ] F5.7 Perfiles destino: Core, bibliotecas/parches permitidos, permiso de instalación y fecha de inventario. TARGET_INCOMPATIBLE explica dependencias ausentes, incluida MathDisplay. Inventario desconocido no se declara compatible.

**Aceptación:** modificar originales no altera preparación; tenant ajeno no enumera/recupera objetos; claves no colisionan entre tenants; TTL y recuperación no publican parciales.

## 10. F6 — Streamable HTTP, autorización y tareas

- [ ] F6.1 Spike de transporte con middleware oficial Hono, Request/Response y Bun.serve contra versiones fijadas; /mcp con negociación y ciclo real del SDK, sin copiar supuestos del antiguo SSE. Conformidad HTTP en CI.
- [ ] F6.2 OAuth resource server: metadata, issuer/audience/scopes, expiración/rotación y bearer por petición; TLS, Origin/Host y DNS rebinding donde aplique. Seleccionar proveedor tras requisitos.
- [ ] F6.3 Scopes h5p:read/author/export/validate/admin:libraries aplicados en casos de uso. Tenant deriva de identidad autenticada, no de argumento libre.
- [ ] F6.4 REST mínimo para uploads/downloads y jobs si hace falta; mismos stores/casos de uso. Administración ausente en modo inmutable; borrado explícito y autorizado.
- [ ] F6.5 Límites body/tiempo/memoria de worker/disco, jobs por usuario/tenant, cola y concurrencia global; backpressure. Muchos lotes pequeños también consumen cuota.
- [ ] F6.6 Egress cerrado por defecto. Instalaciones solo vía administración autorizada. Si se descargan URLs, bloquear redes privadas/metadata, redirecciones y cambios DNS; preferir uploads. Medios remotos de playback no se descargan implícitamente.
- [ ] F6.7 Tasks solo cuando se negocie y el SDK/cliente lo soporte: estados, progreso, cancelación, TTL, recuperación. Fallback a lote síncrono pequeño o jobs propios explícitos; no anunciar tasks/* ficticios.
- [ ] F6.8 Logs correlacionados por operación/job/tenant sin tokens, rutas sensibles ni material educativo completo. Métricas de cola, bytes, memoria, errores, duración y cancelación.
- [ ] F6.9 Adversariales: ZIP traversal/bomb, MIME falso, abuso de IDs/scopes/tokens, SSRF, concurrencia y prompt injection del material. El texto educativo nunca autoriza administración.

**Aceptación:** esquema remoto sin rutas; dos tenants aislados; cancelación libera worker/cuota; reinicio recupera estado; límites durante streaming. No exponer listener público antes del gate y decisión de hosting.

## 11. F7 — Distribución y publicación

- [ ] F7.1 Resolver ADR legal; notices, SBOM, fuente/parches Lumi y bibliotecas conforme a sus licencias antes de distribución pública.
- [ ] F7.2 Pipeline reproducible: instalación frozen de Bun, bun:test, TS7/lint, conformance, bun pm pack, instalación externa y hashes. Publicar en registro npm mediante mecanismo auditado; registro npm no implica instalar npm en runtime. Release Please u otro sistema coherente con Conventional Commits/semver.
- [ ] F7.3 OCI Bun 1.4.2 glibc sobre Debian/Ubuntu compatible, fijada por digest, no-root, aplicación read-only, temporales/artifacts separados y health/readiness sin secretos. Sin bun install, npm install ni descargas H5P al arrancar. Incluir binario N-API correcto para cada arquitectura y probar arranque sin Node/Python.
- [ ] F7.4 SBOM/attestation vinculados a tarball e imagen; análisis de dependencias/contenedor con triage documentado.
- [ ] F7.5 server.json con esquema Registry vigente, paquete npm y remoto solo si realmente disponible; Registry complementa npm/documentación.
- [ ] F7.6 Action opcional de build por lotes: inputs validados, permisos mínimos, retención; nunca backend conversacional.
- [ ] F7.7 Guías local/remoto/seguridad/licencias/soporte/rollback/uvx→bunx. Publicación del artefacto concreto autorizada y credenciales de alcance mínimo.

**Aceptación:** instalación fijada sin checkout, imagen arranca sin red de instalación, SBOM verificable y rollback probado. No actualizar MCP activo como efecto colateral.

## 12. F8 — Evaluación educativa, IA y Moodle

- [ ] F8.1 Corpus: elección por objetivo pedagógico, español, anidados, reparación de select, imagen, matemáticas, biblioteca ausente/no verificada, lote e incompatibilidad Moodle.
- [ ] F8.2 Registrar modelo/cliente/versiones/prompts/fixtures: task_success_rate, first_prepare_success_rate, mean_tool_calls, schema_repair_loops, invalid_field_rate, tools_list_tokens, schema_response_tokens, p50/p95, artifact_validation_rate y digest reproducible bajo inputs fijados. Separar variación LLM de determinismo del núcleo.
- [ ] F8.3 Acierto/error/parcial/reintento/finalización por tipos representativos; MathDisplay visible sin errores en ambas ramas. No generalizar resultado TF a todas las actividades.
- [ ] F8.4 Moodle 5.1.x real: versión parche, core/mod_hvp, Core, bibliotecas y permisos. Probar importación, reproducción, intentos, persistencia y gradebook con alumno en curso autorizado.
- [ ] F8.5 Accesibilidad independiente: teclado/foco/labels/lector/matemáticas. Registrar límites por actividad/versión.
- [ ] F8.6 Evaluar calidad conceptual, feedback y distractores aparte de conformidad técnica.

**Aceptación:** evidencia por check/entorno/actividad; not_run donde no haya acceso. Local puede cerrarse sin Moodle, pero moodle_grading no se anuncia sin prueba real.

## 12B. F9 — Ejecutable autónomo opcional, posterior a la estabilización

- [ ] F9.1 Spike de `bun build --compile` por SO/arquitectura ya certificados, después de F7. No convertirlo en requisito para entregar tarball/OCI.
- [ ] F9.2 Verificar carga/empaquetado de N-API, ubicación de Lumi, recursos Skills y bibliotecas dinámicas. Mantener datos del usuario y bibliotecas instalables fuera del ejecutable.
- [ ] F9.3 Ejecutar en máquina limpia sin Bun/Node/Python instalados: stdio, export/import, medios, fórmulas y permisos. Compilación cruzada exitosa no sustituye ejecución en destino.
- [ ] F9.4 Firma de binarios, checksums, SBOM/fuente/notices, actualización y rollback por plataforma. Si no se cumple, distribuir tarball/OCI certificados sin prometer binario autónomo.

**Aceptación:** mismas garantías y licencias que el paquete normal, sin archivos del checkout y con evidencia de ejecución en cada destino anunciado.

## 13. Matriz de aceptación transversal

| Área | Positivos | Negativos/fallos | Evidencia |
|---|---|---|---|
| Semántica | Defaults, aplanados, anidados, español, TeX | regexp, decimales/step aplicables, tipos, UUID, profundidad | Unitarias + diferencial Lumi |
| ZIP/medios | H5P válidos y formatos permitidos | Traversal, symlink, alias, ratio, MIME falso | Unitarias acotadas + worker |
| Preparación | Snapshot, IDs preservados, idempotencia | Cambios de medios/libs, TTL, clave en conflicto | Digests y recuperación |
| Publicación | Exportación e importación vacía | Dos escritores, cancelación, filesystem sin links | Sin overwrite/parciales |
| MCP | stdio, HTTP, recursos, Skills | Cliente sin extensión, inputs inválidos, scopes | Conformance + clientes fijados |
| Distribución | Wheel transitorio, tarball Bun en registro npm, OCI | Checkout/caché ausentes, inicio sin red | CI por SO/runtime |
| Remoto | Dos tenants y scopes correctos | ID ajeno, SSRF, token expirado, abuso de carga | Autorización y cuotas |
| Educación | Feedback, scores y reintentos | Respuestas incorrectas y TeX inválido | Navegador + Moodle autorizado |

## 14. Unidades de commit, dependencias y rollback

Cada fila es una unidad integrable con pruebas; una fase puede requerir varios commits. Los mensajes son propuestas, no commits ya realizados. Cada implementación incluye sus pruebas en el mismo commit; no dejar commits rojos deliberados. Fases de producto se mantienen opt-in hasta su gate. No commitear outputs de benchmarks, paquetes generados o secretos, salvo fixtures justificadas y reportes compactos reproducibles.

| Orden / fase | Commit Conventional propuesto | Alcance y dependencias | Verificación antes del commit |
|---|---|---|---|
| C01 / F0 | docs(architecture): record runtime and licensing baseline | ADR y baseline; primero | Inventario y referencias, estado real |
| C02 / B0 | build(bun): pin experimental runtime and dependency lock | Sandbox de Bun, sin tocar producción; C01 | frozen install, hashes y scripts deshabilitados |
| C03 / B0 | test(runtime): compare Bun and Node H5P behavior | Harness, CRC32, ZIP y medios; C02 | Paridad con fixtures de IDs fijados |
| C04 / B0 | ci(bun): certify runtime on supported platforms | Matriz y reportes; C03 | Sintaxis CI y ejecución verde para promoción |
| C05 / F1 | fix(archive): enforce portable extraction budgets | ZIP/rutas/symlinks; C01 | Fronteras y archivos adversariales |
| C06 / F1 | fix(media): verify asset signatures and access roots | MIME/raíces; C05 | Firma falsa, symlinks y medios válidos |
| C07 / F1 | fix(authoring): complete semantic and graph checks | Reglas/HTML/grafo; C05 | Diferencial H5P y LaTeX sin alteración |
| C08 / F1 | fix(jobs): cancel workers and publish exclusively | Deadline/publicación; C05–C07 | Cancelación, carreras y FS sin hardlinks |
| C09 / F1 | ci: enforce packaged regression and artifact hygiene | Limpieza y matriz; C04/C08 | Wheel legado, navegador y guardias |
| C10 / F2 | feat(contracts): define versioned reports and diagnostics | Esquemas/adaptadores compatibles; C09 | Snapshots y errores MCP |
| C11 / F2 | feat(admin): separate library administration from queries | Nuevas tools + aliases locales; C10 | Autorización directa y consultas puras |
| C12 / F2 | feat(discovery): expose compact contracts and evidence | Catálogo/recursos; C10/C11 | Proyección semántica y referencias |
| C13 / F3 | refactor(core): port pure authoring rules to TypeScript | TS7/bun:test, código opt-in; C04/C12 | Corpus Python/Node/Bun equivalente |
| C14 / F3 | refactor(lumi): isolate persistent engine and job stores | Adaptador CJS y scheduler; C13 | Import/export, locks entre procesos, benchmark |
| C15 / F4 | feat(mcp): add Bun stdio adapter with legacy parity | Proceso persistente opt-in; C14 | Tools/CLI/errores/stdio conformes |
| C16 / F4 | feat(skills): serve progressive authoring resources | Recursos y ejemplos; C15 | Digest, traversal, cliente sin extensión |
| C17 / F4 | build(package): verify Bun tarball distribution | dist, bin, dependencias; C15/C16 | Instalación externa sin Node/Python |
| C18 / F4-R | feat(runtime)!: switch default server to Bun | Cambio público deliberado; C17 + gate F4 | Matriz completa, migración y rollback |
| C19 / F4-R | refactor(runtime): remove obsolete Python bridge | Retirada, única autoridad bun.lock; C18 | Corpus Bun completo, oráculo CI preservado |
| C20 / F5 | feat(storage): add immutable preparations and artifacts | Stores/perfiles/TTL; C10/C14 | Snapshot, drift e idempotencia concurrente |
| C21 / F5 | feat(tenancy): authorize object access and quotas | ownership/límites; C20 | Dos tenants, expiración, recuperación |
| C22 / F6 | feat(http): add authenticated Hono MCP transport | Bun.serve y OAuth; C18/C21 | Conformance HTTP, Origin, scopes, egress |
| C23 / F6 | feat(tasks): expose negotiated cancellable jobs | Solo tras spike SDK/cliente; C22 | Estados, cancelación, fallback y reinicio |
| C24 / F7 | build(container): package immutable Bun runtime | glibc/seguridad; C22 + gate legal | OCI sin instalación al inicio, SBOM |
| C25 / F7 | ci(release): attest packages and publish metadata | Pipeline/Registry; C17/C24 | Dry-run verificable; publicación autorizada aparte |
| C26 / F8 | test(evaluation): compare agent and Moodle outcomes | Corpus desde F0, reporte tras C18/C22 | Métricas y checks con entorno/versiones |
| C27 / F7 | docs(migration): document Bun operations and rollback | Guías finales; C18–C26 aplicables | Comandos ensayados y soporte exacto |
| C28 / F9 | build(binary): add certified standalone artifacts | Opcional tras F7 | Binario ejecutado en cada destino |

C05–C08 pueden avanzar aunque B0 esté bloqueado; C13 no. C20 puede avanzar después de C14 sin esperar a retirar Python. C26 tiene un corpus inicial en C01/C03 y se amplía progresivamente. C23 se difiere si Tasks no está soportado, conservando jobs propios explícitos. Un revert requiere retirar primero commits dependientes; no borrar stores ni snapshots del usuario.



- Un bloque implementable por commit. fix para correcciones del producto; feat para capacidades; test/ci/docs para su alcance. Rupturas con ! y guía de migración. Revisar configuración de releases antes de commitear.
- Secuencia: baseline → B0 → robustez y contratos → núcleo TS/Bun → stdio/Skills/tarball → gate de retirada Python → stores/HTTP → distribución; F8 acompaña el proceso y F9 es opcional.
- Ejecutar pruebas proporcionales por bloque y matriz completa antes de cambiar runtime predeterminado. No modificar archivos durante una ejecución que se presentará como evidencia final.
- Conservar release Python y snapshot previo durante la transición; Node solo como referencia CI tras F4-R, sin fallback silencioso en producción Bun. Rollback selecciona binario/snapshot anterior sin transformar ni sobrescribir contenido del usuario.
- Si un gate falla, registrar reproducción y conservar runtime anterior. No convertir defectos de seguridad en warnings ni avanzar al despliegue remoto.
- Push, publicación npm/OCI, release y cambio de configuración activa son acciones diferentes. No inferir todas de la aprobación del plan.

## 15. Criterio global de cierre

- [ ] F0/B0/F1–F4 y F4-R locales cerradas con paridad, benchmark y prueba de runtime Bun efectivo.
- [ ] F5–F6 verificadas antes de habilitar servicio remoto.
- [ ] F7 resuelta para cada artefacto a publicar, incluidas licencias.
- [ ] F8 reporta checks reales y pendientes de Moodle/accesibilidad.
- [ ] Migración/rollback documentados; sin dependencia de caché o temporales personales.
- [ ] Commits revisables, árbol sin artefactos accidentales e incertidumbres explícitas.
- [ ] F9 solo se marca terminado si hay ejecutables certificados; se puede cerrar la entrega principal dejando F9 explícitamente diferida.

## Fuentes y verificación documental

Consultadas al preparar el plan, 2026-09-19:

- [SDK TypeScript: roadmap oficial](https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/ROADMAP.md): v2 estable, revisión 2026-07-28 y Tasks como extensión independiente. Fijar versión exacta en F0.
- [Node.js: releases](https://nodejs.org/en/about/previous-releases): Node 24 y 22 figuran LTS, 26 Current al consultar. Revisar de nuevo al fijar matriz.
- [Skills extension](https://raw.githubusercontent.com/modelcontextprotocol/ext-skills/main/README.md): especificación estable SEP-2640; modelar recursos conforme a ella.
- [Apache/GPL compatibility](https://www.apache.org/licenses/GPL-compatibility): motiva revisión de distribución combinada; no resuelve por sí sola el caso legal del proyecto.

Referencias de trabajo de la auditoría que deben verificarse y fijarse en sus spikes:

- [Conformance MCP](https://github.com/modelcontextprotocol/conformance).
- [Tools MCP](https://modelcontextprotocol.io/specification/2026-07-28/server/tools).
- [Autorización MCP](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization).
- [Tasks](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks).
- [H5P semantics](https://h5p.org/semantics).
- [OWASP File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html). La referencia [1] de la auditoría enlaza Input Validation aunque describe File Upload; distinguir ambas al construir pruebas.
