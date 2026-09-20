import type {CoreRequest,Native} from '../domain/types.js';
import {projectSemantics} from '../domain/contracts.js';
import {query} from './catalog.js';
export async function nativeContract(request:CoreRequest) {
 const raw:Native=await query({...request,action:'schema'});
 return {library:raw.library,patch_version:raw.patch_version,...projectSemantics(raw.semantics)};
}
