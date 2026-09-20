# F5 — Persistencia local e inmutabilidad

El workflow persistente complementa los contratos locales existentes. `upload_h5p_asset` → `prepare_stored_h5p_activity` → `export_prepared_h5p_activity` devuelve IDs opacos y recursos persistentes. Los contratos están en `h5p-contract://v1/storage`; la skill explica el uso.

| Garantía | Implementación |
|---|---|
| F5.1 Ownership | Principal del host, tenant y owner en cada acceso; entradas cerradas sin identidad elegida por el cliente. Stdio usa `local/local`. |
| F5.2 Upload | Streaming a staging, 64 MiB por medio / 128 MiB por paquete, firma/MIME y preflight ZIP aislado antes de publicar. |
| F5.3 Preparación | Parámetros normalizados, medios copiados y snapshot de bibliotecas; manifiestos SHA-256 verificados en cada lectura. |
| F5.4 Idempotencia | Clave y digest por tenant/owner, reserva SQLite y reutilización tras reinicio; conflicto si cambian inputs. |
| F5.5 Artefactos | SQLite WAL/FULL como barrera de publicación después de rename; TTL, revocación y recuperación de staging abandonado. Recursos MCP autorizados por principal, sin URL pública. |
| F5.6 Bibliotecas | `libraries.lock.json` por generación con versiones/parches/hashes y evidencia observada. Procedencia upstream desconocida declarada como tal. Captura y activación requieren administración. |
| F5.7 Destino | Inventario fechado, Core, parches, política opcional y permiso de instalar. Ausencia de inventario nunca significa compatible; MathDisplay se comprueba como dependencia. |

## Operación

`H5P_MCP_STORE_DIR` selecciona el directorio privado; por defecto `<H5P_MCP_DATA_DIR>/objects`. No compartirlo mediante HTTP ni editar sus objetos. Respaldar SQLite y los objetos como una unidad consistente con el proceso detenido. No se cambia la configuración del MCP activo.

TTL predeterminado: 24 horas; snapshots: un año. Los perfiles de destino caducan desde `inventory_at`, no desde su registro. Cada objeto admite hasta 512 MiB y 20 000 archivos; cada tenant tiene 2 GiB y 4096 registros. Cada escritura reserva 512 MiB hasta publicar, limitando también staging concurrente. Revocar libera bytes; tombstones y claves se retienen hasta 24 horas después de expirar/revocar, luego pueden reutilizarse las claves. La limpieza ocurre al abrir el store y antes de publicar. Una caída requiere esperar el lease de cinco minutos para recuperar el staging; nunca expone el resultado parcial. La prueba de recuperación cubre caída de proceso, no corte eléctrico del sistema de archivos.

Cambiar la generación activa afecta a futuras preparaciones persistentes; no modifica preparaciones existentes ni restaura la carpeta mutable usada por herramientas locales antiguas. Cada preparación requiere que su snapshot siga disponible. Revocar una generación puede invalidar las preparaciones que la necesitan; los artefactos ya publicados son independientes.

La lectura MCP limita respuestas a 16 MiB por defecto. HTTP/OAuth, descarga autenticada remota y cuotas por solicitud corresponden a F6. Aquí se prueba aislamiento de los stores con principals distintos; no se anuncia aislamiento remoto ni verificación de reproducción/calificación en Moodle.

## Evidencia reproducible

- `bun test tests/core`: ownership, TTL, revocación, integridad, cuotas, carrera idempotente y caída real de un subprocess entre rename y commit SQLite.
- `tests/tooling/package-probe.ps1`: instala tarball externo y usa clientes SDK reales. El probe F5 altera los originales, exporta desde snapshot, valida el paquete con Lumi, comprueba MathDisplay, reinicia el proceso, recupera el mismo artefacto y prueba rollback/revocación.
- La matriz existente ejecuta ambos grupos en Windows, Linux y macOS. Una ejecución pendiente no se considera certificación.
