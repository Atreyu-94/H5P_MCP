# F6 — HTTP protegido optativo

El mismo registro MCP sirve stdio y HTTP. HTTP usa Hono 4.13.8, middleware oficial `@modelcontextprotocol/hono` 2.0.0, el SDK 2.0.0 y jose 6.2.12. El handler oficial negocia tráfico moderno y legacy stateless. No hay sesiones persistentes ni Tasks: las operaciones son síncronas, acotadas y cancelables; exportación se recupera mediante el ID preparado y la clave idempotente de F5.

## Configuración del host

`h5p-mcp http <ruta-absoluta/config.json>` inicia **solo en 127.0.0.1**. No se cambia el cliente activo ni se despliega un endpoint público. Para producción hace falta decidir hosting y terminar TLS en un proxy local que preserve Host, propague desconexión y limite cuerpo/tiempo/conexiones. No se confía en X-Forwarded-*.

```json
{
  "resource": "https://h5p.example.org/mcp",
  "issuer": "https://identity.example.org/realms/school",
  "jwksFile": "D:/h5p-host/public-jwks.json",
  "data": "D:/h5p-host/tenants",
  "store": "D:/h5p-host/objects",
  "origins": ["https://client.example.org"],
  "tenantClaim": "tenant_id",
  "immutable": true,
  "port": 3000
}
```

El proveedor elegido debe emitir **access JWT RFC 9068** con `typ: at+jwt`, firma RS256 o ES256, `iss`, `aud` igual a resource, `exp`, `sub`, `scope` separado por espacios y el claim de tenant configurado. Se comprueba `nbf` cuando existe. Tokens opacos e ID tokens no se aceptan. Este servicio verifica tokens; no emite tokens ni implementa el login del proveedor.

JWKS es un archivo de **claves públicas**, máximo 256 KiB/32 claves, provisionado por el administrador desde su proveedor OIDC. Reemplazarlo atómicamente permite rotación: cada petición verifica el contenido actual, sin conservar aceptación de claves retiradas. No hay descubrimiento ni descarga automática de JWKS; tampoco se siguen jku/x5u del token. Esto mantiene el egress cerrado. La integración con un proveedor real y su flujo de consentimiento no se ha probado; las pruebas generan claves locales.

El challenge 401 apunta a `/.well-known/oauth-protected-resource/mcp`. Metadata anuncia resource, issuer y scopes. Bearer se exige en cada petición operativa, incluida la descarga. Host debe coincidir exactamente, puerto incluido; Origin, si existe, debe pertenecer a la lista exacta. HTTPS es obligatorio en resource salvo loopback de pruebas. No se aceptan tokens en query.

## Superficie remota

Todas las operaciones requieren `h5p:read`, más el scope específico:

| Scope | Operaciones |
|---|---|
| `h5p:read` | Descubrimiento instalado, contratos/Skills, listado y recursos propios, descarga |
| `h5p:author` | Upload de medios, preparación, perfil destino, revocación de objetos propios |
| `h5p:export` | Exportar una preparación propia con idempotency_key |
| `h5p:validate` | Upload e importación de paquetes propios |
| `h5p:admin:libraries` | Instalar paquete por ID, capturar/activar snapshots; requiere immutable=false |

Revocar un snapshot exige también scope administrativo y modo mutable. No se exponen aliases ni argumentos de rutas locales. Bibliotecas mutables viven bajo un namespace derivado de issuer/tenant; ownership usa issuer/sub. Esquemas nativos se guardan con TTL de 24 h y autorización por propietario para sobrevivir entre peticiones.

REST usa cuerpos binarios sin multipart ni nombres elegidos por el cliente:

- `POST /uploads/assets`: MIME del medio en Content-Type, requiere author; devuelve object_id.
- `POST /uploads/packages`: application/zip, requiere validate; devuelve object_id.
- `GET /artifacts/<object_id>`: verifica propietario, TTL e integridad; devuelve H5P, ETag y no-store.

El workflow MCP usa `prepare_stored_h5p_activity`, `export_prepared_h5p_activity` y `validate_stored_h5p_package`. Puede instalarse un paquete autorizado con `install_h5p_library_package({object_id})`; nunca se descargan bibliotecas del Hub por HTTP. Las URLs de medios se conservan para playback, sin descarga del servidor. El contenido educativo no concede scopes.

## Límites y recuperación

Un proceso por store. Dos operaciones activas globales y ocho en cola; máximo dos solicitudes por usuario y cuatro por tenant; 120 solicitudes autenticadas por tenant/minuto, incluido fallo o lote pequeño. Autenticación tiene ocho verificaciones concurrentes sin cola. No hay batches JSON-RPC ni jobs en background.

Cuerpo MCP máximo 1 MiB, respuesta MCP 16 MiB, medio 64 MiB y paquete 128 MiB. Lecturas de cuerpos son incrementales y rechazan content-encoding. Deadline de cinco minutos o expiración del token, el menor. Cancelación del cliente/shutdown llega al worker; el permiso de ejecución y la cola se liberan después de recogerlo. Los controles ZIP/MIME y presupuestos del núcleo se conservan.

El store reserva bytes para staging: 2 GiB/4096 registros por tenant, 8 GiB/32768 globales. Estas cuotas cubren objetos, no la carpeta de bibliotecas mutable del administrador, temporales de Lumi o una garantía de RSS del SO. Antes de hosting público, F7 debe aplicar cuotas del volumen y límite de memoria/procesos del contenedor. No se anuncia escalado multiproceso: las cuotas de peticiones son locales al proceso. El límite de objetos es transaccional SQLite.

Los logs incluyen UUID de operación, tenant derivado, clase de ruta, status, duración, bytes de entrada, cola, concurrencia y RSS; omiten tokens, IDs de usuario, rutas, argumentos y contenido educativo. Contadores agregados están disponibles al host en el handler, sin endpoint público de métricas. Los estados publicados y la idempotencia se recuperan en SQLite; una petición interrumpida se reintenta con la misma clave, no se anuncia como Task recuperada.

## Verificación y límites de la evidencia

`tests/core/http.test.ts` cubre tokens, audience/issuer/exp/nbf, rotación, scopes, Host/Origin, aislamiento tenant/owner, MIME/cuerpo, cancelación y admisión. La suite ZIP adversarial del núcleo sigue activa.

`tests/tooling/http-probe.mjs` usa listeners efímeros de loopback contra el tarball instalado: cliente SDK moderno/legacy, contratos persistentes, export/import, administración por ID, aislamiento y reinicio. Se integra en el CI Windows/Linux/macOS.

Conformance oficial **0.1.16** ejecuta `server-initialize`, `ping`, `tools-list`, `resources-list`. Esa versión cubre aquí el protocolo legacy; no certifica íntegramente 2026-07-28. Como su CLI no admite headers bearer, un proxy exclusivo de la prueba inyecta el JWT de prueba; autenticación se prueba directamente y permanece obligatoria en producto. No confundir este subconjunto con conformidad total o certificación OAuth del proveedor. Tasks queda diferida; el fallback síncrono está implementado.

Fuentes contrastadas con los tipos y código instalados: [adaptador oficial Hono](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/packages/middleware/hono/README.md), [resource server y bearer por petición](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/serving/authorization.md), [conformance](https://github.com/modelcontextprotocol/conformance).
