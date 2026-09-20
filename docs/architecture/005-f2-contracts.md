# F2 — Contratos incrementales

## F2.1–F2.4: preparación local y diagnósticos v1 (parcial)

La autoridad contractual está en `h5p_mcp/contracts/v1.json` y el mapping en
`codes-v1.json`. Python valida con JSON Schema 2020-12; la migración TypeScript
consumirá los mismos archivos. No son esquemas de las actividades: `params`
permanece dinámico y se contrasta con las semánticas nativas instaladas.

`prepare_h5p_activity` recibe el contrato `prepare_local_input`. En éxito retorna
una actividad compatible con `export_h5p`, incluido su manifest. No emite un
`preparation_id`: su persistencia, expiración y ownership pertenecen a F5.
La interfaz anterior continúa disponible. Los recursos MCP
`h5p-contract://v1/schema` y `h5p-contract://v1/codes` entregan la autoridad empaquetada.

Una validación negativa retorna `ok=false`, `kind=validation`, `isError=false`.
Un fallo operativo retorna `kind=operational_error`, `isError=true`. La cancelación
se propaga. Los diagnósticos contienen código, JSON Pointer, mensaje público,
expected/actual acotados, retryable y suggested_fix. Los errores internos completos
quedan en el logging local; las respuestas no copian mensajes del backend,
rutas de archivos, valores del alumno ni transformaciones completas. Los punteros
se construyen desde segmentos, sin interpretar las antiguas rutas con puntos.
El puntero vacío representa el documento; si supera 4096 caracteres se informa
la raíz en vez de truncarlo hacia un campo distinto. Hay un máximo de 100
diagnósticos y un indicador de truncación. En error no se devuelve la actividad.

El mapping cubre los códigos del plan y mantiene aliases explícitos; no infiere
códigos a partir de palabras en mensajes internos. Los códigos de archivo, Hub y
exportación se aplicarán a sus nuevas interfaces en los siguientes incrementos.
No se afirma aún paridad contractual vNext para validación de paquetes o batch.

Verificación de F2.1–F2.4 (`0e2093c`, `9ad543b`): 113 pruebas iniciales con dependencias bloqueadas; después,
114 pruebas de la suite completa pasaron desde el wheel instalado fuera del
checkout en Windows con Lumi aislado. La instalación del wheel resolvió
FastMCP 4.0.5 dentro del rango permitido (el lock fija 4.0.3). Incluyen cliente
MCP, preparación real, exportación por stdio, errores operativos simulados,
ausencia de datos sensibles, límite de diagnósticos, Unicode/escapes y paridad
de JSON Pointer entre Python y JavaScript. No es una nueva prueba en Moodle.

## Cierre del gate previo

El commit `7bb52c55d3424fc3a44f32046a334fe623c5858a` pasó en el fork del usuario:

- [Paquete y navegador](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35487170040).
- [Matriz Bun/Node](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35487170079).

La evidencia cierra B0/F1 para los destinos definidos; no certifica Linux arm64,
musl ni la futura implementación TypeScript.

## F2.5: administración local separada

`search_h5p_types` consulta sin flags de instalación o actualización. Se añaden
`refresh_h5p_catalog`, `install_h5p_library` e `install_h5p_library_package`.
El proceso local fija al iniciar sus scopes administrativos mediante
`H5P_MCP_ADMIN_SCOPES`: `catalog:refresh` y `libraries:install`, separados por
espacios. Por defecto no concede ninguno. El segundo scope permite contactar
al Hub y actualizar su caché cuando sea necesario para instalar una biblioteca.
El paquete local pasa autorización de ruta y preflight ZIP antes del importador.
Puede actualizar bibliotecas existentes; no es una instalación transaccional.

El middleware filtra el listado y rechaza la invocación incluso en stdio.
Las funciones Python administrativas y los flags legados comprueban la misma
política. `H5P_MCP_IMMUTABLE=1` prevalece sobre los scopes y también bloquea el
comando `--setup-lumi`. La configuración pertenece al host, no a argumentos del
LLM. No constituye OAuth, aislamiento entre tenants ni sandbox del sistema.
La API Python interna del backend sigue siendo código de confianza del host.

Lumi inicializa directorios incluso para lecturas. Por ello las consultas usan
una copia temporal de configuración/caché y almacenamiento temporal eliminado
al terminar. Las bibliotecas instaladas se leen en su ubicación original; una
consulta sin bibliotecas no crea ese directorio. El lock de coordinación puede
crearse y sigue serializando consultas con instalaciones; no es estado de autoría.
Las anotaciones describen efectos, pero la autorización no depende de ellas.

Las 27 pruebas iniciales de administración/descubrimiento pasaron: rechazo por
scope, modo inmutable, stdio real, flags legados, instalación real en almacén
vacío, ZIP inseguro y rutas no autorizadas, consultas sin red y sin cambios en
contenido de caché/configuración/bibliotecas. La skill empaquetada se actualizó
para enseñar el flujo administrativo y pasó `quick_validate.py`.

Cierre local de F2.5 (`bbf8c7e`): suite completa con 128 pruebas aprobadas; 30 pruebas adicionales
de administración, descubrimiento, skill y stdio aprobadas desde el wheel
instalado fuera del checkout con dependencias bloqueadas. Build, Oxlint y guardia
de artefactos también pasan. No se cambió la configuración del MCP activo.

CI de F2.1–F2.4 (`9ad543b`) confirmado en verde durante la implementación de F2.5:

- [Paquete y navegador](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35488159953).
- [Matriz Bun/Node](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35488160084).

F2.6 y F2.7 continúan pendientes: proyección compacta de semánticas, recursos
brutos y evidencia del catálogo. Tampoco se da por cerrada F2 en su conjunto.
