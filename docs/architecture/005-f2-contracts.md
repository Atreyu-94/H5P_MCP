# F2 — Contratos incrementales

## C10: preparación local y diagnósticos v1

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

Verificación C10: 113 pruebas de la suite completa pasaron en Windows con Lumi
aislado. Incluyen cliente MCP, preparación real, errores operativos simulados,
ausencia de datos sensibles, límite de diagnósticos, Unicode/escapes y paridad
de JSON Pointer entre Python y JavaScript. No es una nueva prueba en Moodle.

## Cierre del gate previo

El commit `7bb52c55d3424fc3a44f32046a334fe623c5858a` pasó en el fork del usuario:

- [Paquete y navegador](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35487170040).
- [Matriz Bun/Node](https://github.com/Atreyu-94/H5P_MCP/actions/runs/35487170079).

La evidencia cierra B0/F1 para los destinos definidos; no certifica Linux arm64,
musl ni la futura implementación TypeScript.
