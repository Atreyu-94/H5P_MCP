# F4-R — Retirada del runtime Python

El producto usa Bun 1.4.2, SDK MCP 2.0.0 y Lumi Core 1.28. Se retiraron FastMCP,
Pydantic, el servidor/CLI Python, core_client, el puente CJS y sus reglas duplicadas.
El directorio h5p_mcp conserva recursos estáticos por compatibilidad de rutas.
No se modificaron almacenes del usuario, entornos existentes ni configuración MCP.

| Responsabilidad R.1 | Implementación | Verificación |
|---|---|---|
| Modelos y diagnósticos | Contratos JSON/Ajv; punteros y mensajes públicos acotados | service.test.ts, SDK moderno/legacy |
| Semántica, matemáticas y medios | Núcleo TS sobre Lumi; versiones y manifiestos | 9 variantes y 14 comparaciones Node/Bun |
| ZIP | Preflight de todos los miembros: CRC, tipos, rutas, colisiones, tamaños, JSON | retirement.test.ts; importaciones reales |
| Rutas y publicación | Realpath/raíces, staging, hardlink o rename nativo exclusivo | Roots y fallback sin sobreescritura |
| Locks y cancelación | Cola, snapshots cancelables, worker abortado/recolectado, cierre stdio | Pruebas de pool/generaciones/worker y operación pendiente |
| CLI, MCP y Skills | Mismo servicio en CLI/SDK; 13 recursos con digest/allowlist | Paquete externo, CLI export/validate/admin, bunx |

ZIP usa una clave Unicode conservadora NFKC/caseless que puede rechazar más
nombres que el antiguo preflight. No permite colisiones que este admitía por
normalización. Los controles se ejecutan en workers cancelables antes de importar.
El fallback nativo se prueba explícitamente; no se hace una copia parcial al destino.

## R.2–R.7 y rollback

- Lumi y sus dependencias N-API quedan vendorizados en el tarball; dist, Skills,
  licencias y provenance se verifican en instalación externa.
- bun.lock es la autoridad del producto. tests/tooling/package-lock.json pertenece
  únicamente al cliente/oráculo de pruebas. Se retiró el lock npm del runtime anterior.
- Bin principal: h5p-mcp; alias conservado: h5p-mcp-bun. Ambos requieren Bun.
- Rollback congelado: tag python-final-f4, commit
  93060c52195bde9b590dba11e533bdedba3d2cc1. Su CI automático sigue activo,
  incluyendo wheel, navegador y matriz histórica. No se publicó una release npm/PyPI.
- Los archivos Python restantes bajo tests son referencia histórica; sus pruebas
  se ejecutan sobre el checkout congelado, nunca como dependencia del producto.
- El comparador Node/Bun se conserva al menos dos releases estables. Node es
  herramienta de pruebas, sin fallback de ejecución del producto.
- Si el cliente usa uvx siguiendo main, debe migrarse al comando Bun del README
  antes de reiniciar, o fijarse al SHA Python anterior. La configuración activa
  queda bajo control del usuario.

F4 quedó aprobada en CI 35526615814, 35526615796 y 35526615792. F4-R tiene build,
lint, controles locales y ensayo externo aprobados en Windows; su nuevo CI
multiplataforma se registra en el plan. Estos checks no certifican Moodle ni
amplían las afirmaciones de reproducción/calificación de la baseline anterior.
