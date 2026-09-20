# workflow

Start with a learning objective and evidence of understanding. Discover installed types, inspect exact native schemas including nested libraries, prepare, correct diagnostics, export, then validate. Give feedback explaining each misconception; do not equate a valid package with effective pedagogy.

For persistent work:

1. Upload each local medium with upload_h5p_asset(path, mime). Map each symbolic asset name to the returned object_id; native fields still use asset:name.
2. Call prepare_stored_h5p_activity({activity}) with that map and the native content. The returned object_id identifies immutable normalized content, copied media and its library_snapshot_id. Never pass filesystem paths as stored asset IDs.
3. If a verified destination inventory is available, register_h5p_target_profile({profile}) with Core, exact library patches, installation permission and inventory_at. Do not invent an inventory. A profile's TTL counts from the observation date.
4. Call export_prepared_h5p_activity({preparation_id, idempotency_key, target_profile_id?}). Reuse the key only for the same inputs when retrying; change it for a new export. Unknown inventory is explicitly unverified. An incompatible supplied profile blocks export; inspect diagnostic.expected for missing dependencies, including MathDisplay.
5. Read the returned artifact URI. It persists across restarts until expiry or revocation. To independently import-validate downloaded bytes, call upload_h5p_package(path, "application/zip"), then validate_stored_h5p_package({object_id}).

Default object TTL is one day. Renew by creating new objects; expired or revoked objects are not downloadable. list_stored_h5p_objects lists only the current host principal's objects. revoke_stored_h5p_object deletes that object's stored bytes; preparations retain their own media copies. Library administration can capture a new generation or activate an earlier snapshot for subsequent stored preparations; already prepared activities retain their pinned generation. The local stdio host supplies identity; these tools do not establish a remote authenticated service.
