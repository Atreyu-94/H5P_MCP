# F1 — Endurecimiento local

Estado: F1 parcial. La adopción de Bun sigue condicionada a B0. Esta entrega mantiene Python/Node y modifica el validador de paquetes distribuido.

## Contratos implementados

- Tamaño comprimido máximo de 128 MiB antes de abrir el ZIP; configurable con ZIP_ARCHIVE_BYTES.
- Ratio máximo por miembro de 1000, además de los límites absolutos ya existentes. No sustituye el límite de expansión.
- Lectura completa por bloques de 64 KiB con límites por miembro/total y comprobación CRC del lector ZIP antes de llamar a Lumi.
- Rechazo de enlaces/special files, rutas absolutas, unidades, ADS, barras inversas, segmentos vacíos o punto, controles, nombres reservados Windows y caracteres no portables.
- Comparación NFC/casefold de todos los prefijos para detectar colisiones y conflictos archivo/directorio. Se aceptan carpetas explícitas legítimas.
- Profundidad máxima de ruta de 32 segmentos, configurable con ZIP_PATH_DEPTH.

ZipInfo normaliza separadores en Windows. El validador examina orig_filename para no perder la evidencia del nombre original. La regresión correspondiente modifica ambos encabezados de una fixture ZIP para conservar la barra inversa real.

## Validación

26 pruebas offline y 80 pruebas totales pasan en Windows (suite completa: 67,78 s). Casos de frontera de tamaño comprimido debajo/en/encima del límite; ratio excesivo, corrupción CRC, rutas, enlace simbólico, colisiones Unicode/case y carpetas legítimas. Las pruebas con importer simulado verifican exclusivamente la prevalidación; la suite completa también ejecuta imports Lumi reales de las fixtures.

## CI del push 820a99c

El workflow de empaquetado pasó sus cuatro combinaciones Windows/Ubuntu y Python 3.12/3.13. El workflow B0 pasó Windows y macOS ARM64 con ambas versiones Node, y falló Linux en el comparador de instaladores: Bun conservó el addon musl opcional junto al glibc.

La corrección del harness conserva el diff y acepta únicamente ese paquete opcional declarado en Linux glibc, con su versión exacta. Exige además que Node y Bun carguen el mismo binario que npm y pasen el CRC. La corrección pasó localmente en Windows; su rama Linux requiere el nuevo CI. No se interpreta el fallo original como incompatibilidad del runtime ni se declara Linux certificado antes de repetirlo.

## Segunda entrega local

Prevalidación compartida por validación e instalación administrativa; extracción
acotada mediante adaptador de la API fijada de Lumi; MIME por firma de bytes y
rechazo de SVG/HTML; raíces para paquetes, medios y exportaciones; límites de
nodos/aristas/profundidad de dependencias y recorridos de esquemas/defaults.
El plazo incluye espera del lock. La publicación dispone de rename no-replace
para Windows/Linux/macOS cuando el filesystem no admite hardlinks.

Validación local: **90 tests passed**, incluyendo importaciones reales, límite de
extracción, MIME falso, contenido activo, raíces vacías, ciclos y límites del
grafo, deadline bajo contención y carrera de dos publicaciones sin hardlinks.
Suite completa Windows: 74,90 s. El fallback POSIX necesita ejecución en CI.

El CI de `deff523` terminó correctamente: empaquetado en las cuatro combinaciones
y subconjunto Bun en las seis. Runs: `35483991550` y `35483991534`. Incluye la
corrección del alias `/var`→`/private/var` en macOS y la verificación del addon
glibc cargado en Linux; no incluye esta segunda entrega local.

## Pendientes

No se promete eliminar TOCTOU entre preflight/importación: falta snapshot inmutable.
Siguen abiertos contraste semántico, cancelación MCP efectiva, ampliación de CI y
guardia de artefactos. La matriz B0 solo certifica el corpus implementado.
