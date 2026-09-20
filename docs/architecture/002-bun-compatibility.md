# B0 — Compatibilidad Bun, primera ejecución local

> Registro histórico. Para reproducir los probes Python, usar el checkout `python-final-f4`. La matriz actual usa tests/tooling/retirement-parity.mjs.

2026-09-19. Estado: **B0 parcial; Bun no adoptado**. Producto base 30f6719, Windows x64, Node 26.7.0 y Bun 1.4.2. No se ejecutó todavía la referencia Node 22/24 ni la matriz Linux/macOS.

## Resultado verificado

- Descarga oficial Bun 1.4.2 Windows x64 verificada antes de ejecutar: SHA-256 `ce4c17497b2f29712a99d3d53f028de28cd42e3bacb8589599e7f000e49b6405`. Ejecutable temporal, sin modificación de PATH.
- Ambos runtimes cargan el mismo addon `@node-rs/crc32-win32-x64-msvc` 1.10.8. CRC32, CRC32C de `123456789` y CRC32 vacío coinciden con los vectores conocidos.
- Un árbol npm compartido, dos almacenes de bibliotecas copiados de la fixture verificada y cachés idénticas. Catálogo, discover cacheado y schema iguales.
- TrueFalse, Accordion, MultiChoice, Blanks, QuestionSet y TrueFalse matemático: preparación, manifiesto H5P, contenido JSON y hashes de todos los demás archivos del ZIP iguales. UUID de subcontenido fijados solo en las fixtures de paridad.
- Importación cruzada Node→Bun y Bun→Node, además de cada runtime consigo mismo, en almacenamiento vacío: passed. No-overwrite y select inválido: passed.
- Chrome con host Lumi en Node reproduce los seis paquetes exportados por Bun. En el matemático: incorrecta 0/1, correcta 1/1, retry y fórmulas en ambos feedbacks, sin errores capturados. Esto no es prueba de Moodle ni del host de navegador ejecutado en Bun.

Informes: b0-windows-runtime.json, b0-windows-installer.json y b0-windows-browser.json. Cada informe conserva su propio alcance; `not_run` del probe de runtime no invalida la prueba posterior de navegador, documentada separadamente.

## Comparación independiente del instalador

El instalador Bun migró el package-lock sin habilitar scripts. Otra carpeta sin node_modules instaló el bun.lock con `--frozen-lockfile --ignore-scripts --linker hoisted`; su hash no cambió. Ambos árboles contienen 106 paquetes.

El primer comparador detectó 14 diferencias de ubicación, incluyendo https-proxy-agent, agent-base y mime-types. Se conservan en el informe: Bun eleva versiones distintas a la raíz, mientras otras versiones quedan anidadas. La comparación adicional del grafo confirma que **cada paquete resuelve las mismas versiones de sus dependencias declaradas**. No se igualaron ni ocultaron versiones para lograr paridad. Los archivos nativos coinciden por SHA-256.

Esto no certifica todavía todos los bytes/integridades transitivos ni ejecución del corpus completo sobre el árbol Bun. La comparación de runtime utilizó deliberadamente el árbol npm. El archivo b0-windows-installer.bun.lock es evidencia experimental junto al informe; se reproduce mediante installer-probe.py y no es el lock del producto ni un proyecto instalable autónomo.

## Hallazgo: red implícita en discover

Con caché ausente, `ContentTypeCache.get()` de Lumi llama `forceUpdate()` aunque la herramienta haya recibido `refresh=false`. En la primera ejecución un runtime devolvió last_updated=null y el otro obtuvo una fecha del Hub. Inspección del código instalado confirmó la llamada implícita; no era una diferencia de representación de H5P.

El corpus B0 cacheado prepara explícitamente `{contentTypeCache:[], contentTypeCacheUpdate:1}` en ambos almacenes. Posteriormente se corrigió el producto: discover lee JsonStorage directamente, y solo refresh=true llama forceUpdate. Tres regresiones instrumentan HTTP/HTTPS/socket/fetch: caché ausente y antigua no intentan conexiones con refresh=false; refresh=true sí intenta la actualización solicitada. Las 13 pruebas de descubrimiento y la suite completa de 60 pruebas pasan (103,71 s para la suite). La configuración del MCP activo no se ha actualizado.

## Reproducción en PowerShell

Desde la raíz, crear primero una descarga temporal con bootstrap-windows.ps1; su salida JSON contiene executable. El script comprueba plataforma, SHA-256 y versión efectiva.

```powershell
$setup = ./tests/runtime-compat/bootstrap-windows.ps1 -Destination $env:TEMP | ConvertFrom-Json
.venv/Scripts/python.exe tests/runtime-compat/runtime-probe.py --bun $setup.executable --output exports/b0-runtime.json
.venv/Scripts/python.exe tests/runtime-compat/installer-probe.py --bun $setup.executable --runtime-report exports/b0-runtime.json --output exports/b0-installer.json
```

El probe conserva únicamente su directorio temporal propio para diagnóstico y navegador. Las bibliotecas se verifican antes de extraer; scripts de dependencias permanecen deshabilitados. El workflow bun-compat.yml está preparado para el subconjunto de runtime, con Bun exacto y setup-bun fijado por SHA; **no se ejecutó en GitHub**. El job macOS falla explícitamente si el runner no es arm64. Sus resultados no equivalen a certificación completa B0.

## Actualización: CI y tooling local

El CI de `deff523` terminó: `35483991534` pasó seis combinaciones
Windows x64/Linux x64 glibc/macOS ARM64 con Node 22.12.0/24.21.0.
El workflow de wheel `35483991550` pasó sus cuatro combinaciones.
Las referencias anteriores «no ejecutado en GitHub» son históricas.

El spike usa TypeScript 7.0.2, @types/bun 1.4.2, Oxlint 1.83.0 y
oxlint-tsgolint 7.0.2002. Se descartó ESLint: typescript-eslint 8.70.0 exige
TS <6.1. No conservamos TS6 ni alias para satisfacerlo. Oxlint usa typescript-go;
el tsc independiente continúa como autoridad del typecheck. No se afirma
equivalencia de todas las reglas ESLint.

`node tests/tooling/verify-toolchain.mjs` y Bun 1.4.2 pasan: dominio sin globales
Bun, adaptadores con tipos Bun, strict, noUncheckedIndexedAccess,
noImplicitOverride, ES2022 y skipLibCheck=false. Una fixture negativa comprueba
no-floating-promises; el verificador exige ausencia de ESLint en el lock.
Instalación limpia npm ci --ignore-scripts comprobada. La ampliación aún debe
correr en la matriz remota.

Fuentes: [Oxlint con tipos](https://oxc.rs/docs/guide/usage/linter/type-aware),
[tsgolint v7](https://oxc.rs/blog/2026-07-22-type-aware-linting-stable).

## Pendiente antes de adoptar Bun

- Matriz real Windows/Linux/macOS y referencias Node 22.12.0/24.21.0; hashes por plataforma.
- Audio/vídeo y presupuestos dentro del harness diferencial; la suite Python previa no sustituye ejecutar estos casos con Bun.
- Comparación completa de integridades/recursos transitivos; el corpus sobre árbol instalado por Bun ya pasa localmente.
- EOF, backpressure, streams, cancelación/señales, handles y memoria retenida bajo repetición.
- Hub/TLS/proxy explícitos; nueva interfaz MCP todavía no implementada.
- El defecto de red implícita de discover ya está corregido en el checkout y cubierto por regresiones. El runtime del producto sigue Python/Node.

## Ampliación del corpus y corrección distribuida

El informe b0-windows-runtime-expanded.json verifica ahora siete fixtures sobre el árbol npm: agrega una imagen PNG válida. Se comprueba igualdad con los bytes originales, MIME, dimensiones y referencia en content.json. Lumi genera un nombre aleatorio de imagen en cada exportación; el comparador conserva ambos nombres en el informe y normaliza únicamente ese nombre de la fixture tras verificar los datos. No normaliza UUID, otros campos ni archivos arbitrarios.

También se prueban en ambos runtimes STALE_PREPARATION sin publicación, importación rechazada del paquete sin bibliotecas y preparación rechazada por ausencia de MathDisplay. El caso de discover ahora exige una página no vacía de actividades instaladas: comparar dos listas vacías no validaría el contrato.

`--installer-report <informe>` permite repetir el corpus sobre una copia del árbol generado mediante la reinstalación frozen de Bun; verifica el hash del tarball Lumi antes de usarlo. CI incluye ambos árboles y conserva los reportes por separado. No se ha ejecutado esta matriz en GitHub.

La ejecución b0-windows-bun-tree.json también terminó con local_subset=passed: los siete paquetes, CRC nativo, importación cruzada y casos negativos pasan sobre el árbol Bun. Este informe y b0-windows-runtime-expanded.json son la evidencia ampliada actual; los informes anteriores conservan el alcance histórico de seis fixtures.

La suite Python completa tras corregir discover obtuvo 60 passed, y wheel/sdist se construyeron correctamente. Se inspeccionó el wheel para confirmar que incorpora la lectura de caché sin red implícita.
