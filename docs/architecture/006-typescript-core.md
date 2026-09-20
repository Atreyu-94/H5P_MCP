# F3 — Núcleo TypeScript

El núcleo es opt-in y conserva Python como runtime público. Se compila con
TypeScript 7.0.2 strict, usa Bun 1.4.2 y conserva el tarball Lumi/Core 1.28 fijado.
Las reglas, medios, MathDisplay, grafo y manifiestos están portados; la frontera
con parámetros H5P dinámicos y Lumi CJS usa el tipo explícito Native.

Catálogo, contratos, preparación, exportación, validación y administración tienen
módulos separados. La caché compila regexps nativas y conserva semánticas
inmutables por digest, generación y versión del compilador. No pretende convertir
semantics.json en un validador JSON Schema equivalente.

El motor mantiene un pool de dos trabajos y ocho en espera. Cada lector adquiere
una generación privada, con un máximo de cuatro; una generación activa no se
expulsa. Administración y creación de snapshots comparten .core-lock con Python.
El FileLock legado se conserva. Un cierre abrupto puede dejar .core-lock:
se falla por timeout, sin borrar automáticamente un lock posiblemente activo.

Preparación, exportación e importación usan procesos terminables y staging propio.
La publicación del núcleo usa hardlink exclusivo y falla de forma segura si el
filesystem no lo admite; el adaptador Python conserva su fallback nativo.
Los manifiestos incluyen también hashes del código compilado del núcleo.

El IPC JSON-lines es interno, correlacionado y acotado; CoreClient permite
compararlo desde Python. No es el servidor MCP de F4 ni un servicio remoto.
La persistencia de generaciones entre reinicios y ownership siguen en F5.

## Verificación

Resultados locales y mediciones A/B/C: f3-local-summary.json. A es el backend
Python/Node legado; B y C ejecutan el mismo núcleo persistente con Node y Bun.
Se conservan workers aislados en ambos. Las pruebas verifican JSON, dependencias,
parches, hashes de medios, UUID, diagnósticos e importación en almacenamiento vacío.
Solo se normalizan fechas de observación, nombres generados de medios después de
verificar bytes y la procedencia adicional del código portado.

El CI de F3 ejecuta build, lint, bun:test y paridad en Windows, Linux y macOS.
Los resultados de una plataforma no certifican las demás. No se ha cambiado
la configuración del MCP activo ni se ha publicado un paquete npm.

En Windows pasaron 139 pruebas del wheel, 6 del núcleo/IPC, 9 proyecciones
nativas y 9 fixtures A/B/C. El navegador verificó matemáticas en feedback,
reintento y puntuación 0/1 → 1/1 sin errores.

Medianas de catálogo: A 399 ms, B 320 ms, C 153 ms. Lote de 100 exports:
A 67,6 s, B 92,9 s, C 75,7 s. La primera adquisición de snapshot costó
13–14 s; las siguientes reutilizan la copia pero verifican el árbol fuente.
La copia inicial, la verificación y los workers conservados explican el coste
adicional frente al legado. Se acepta ese coste para preservar aislamiento
y coexistencia con el almacén mutable de Python; no se promueve el runtime
por una supuesta mejora general. F5 podrá reutilizar generaciones persistentes.
Las mediciones preceden los últimos guards de backpressure y tamaño de metadata;
el build y las pruebas finales sí incluyen esos guards. No se repitió toda la
medición por cambios que no alteran el corpus ni el scheduler.

```powershell
bun install --frozen-lockfile --ignore-scripts
bun run build
bun run lint
bun test tests/core
uv run python tests/core/parity.py --bun (Get-Command bun).Source --output f3-parity.json
```
