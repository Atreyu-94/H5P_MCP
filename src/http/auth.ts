import path from 'node:path';
import {createLocalJWKSet,jwtVerify,type JSONWebKeySet} from 'jose';
import {OAuthError,OAuthErrorCode,type AuthInfo} from '@modelcontextprotocol/server';
import {readBounded} from '../infrastructure/media.js';
import {digest,type Principal} from '../storage/objects.js';

export interface HttpConfig {
 resource:string;issuer:string;jwksFile:string;data:string;store:string;
 origins:string[];tenantClaim:string;immutable:boolean;port:number;
}
export const scopes=['h5p:read','h5p:author','h5p:export','h5p:validate','h5p:admin:libraries'];
export function config(value:unknown):HttpConfig {
 const v=value as HttpConfig;
 if(!v||typeof v!=='object'||Object.keys(v).some(k=>!['resource','issuer','jwksFile','data','store','origins','tenantClaim','immutable','port'].includes(k)))throw new Error('Invalid HTTP configuration');
 const resource=new URL(v.resource),issuer=new URL(v.issuer);
 if(resource.username||resource.password||resource.search||resource.hash||resource.pathname!=='/mcp'||issuer.username||issuer.password||issuer.search||issuer.hash)throw new Error('Invalid OAuth URLs');
 if(issuer.protocol!=='https:'||resource.protocol!=='https:'&&!(resource.protocol==='http:'&&['127.0.0.1','localhost','[::1]'].includes(resource.hostname)))throw new Error('HTTPS required');
 if(![v.jwksFile,v.data,v.store].every(p=>typeof p==='string'&&path.isAbsolute(p)))throw new Error('Absolute host paths required');
 if(v.origins!==undefined&&(!Array.isArray(v.origins)||v.origins.length>20||v.origins.some(o=>new URL(o).origin!==o)))throw new Error('Invalid origins');
 if(v.immutable!==undefined&&typeof v.immutable!=='boolean')throw new Error('Invalid immutable mode');
 if(v.tenantClaim!==undefined&&!/^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(v.tenantClaim))throw new Error('Invalid tenant claim');
 const port=v.port??3000;if(!Number.isSafeInteger(port)||port<0||port>65535)throw new Error('Invalid port');
 return {...v,origins:v.origins||[],tenantClaim:v.tenantClaim||'tenant_id',immutable:v.immutable??true,port};
}
export interface Identity extends AuthInfo {extra:{principal:Principal}}
/** Offline verification: only host-supplied public JWKS, atomically replaceable for rotation. */
export function verifier(settings:HttpConfig) {
 let prior='',keys:ReturnType<typeof createLocalJWKSet>;
 return {async verifyAccessToken(token:string):Promise<Identity> {
  try {
   if(token.length>16384)throw new Error('Token too large');
   const bytes=await readBounded(settings.jwksFile,262144),hash=digest(bytes.toString('utf8'));
   if(hash!==prior){
    const jwks=JSON.parse(bytes.toString('utf8')) as JSONWebKeySet;
    if(!Array.isArray(jwks.keys)||!jwks.keys.length||jwks.keys.length>32||jwks.keys.some(k=>!['RSA','EC'].includes(k.kty!)||'d' in k))throw new Error('Public asymmetric keys required');
    keys=createLocalJWKSet(jwks);prior=hash;
   }
   const {payload,protectedHeader}=await jwtVerify(token,keys!,{issuer:settings.issuer,audience:settings.resource,algorithms:['RS256','ES256'],requiredClaims:['exp','sub','iss','aud','scope',settings.tenantClaim]});
   if(protectedHeader.typ!=='at+jwt')throw new Error('Access token required');
   const tenant=payload[settings.tenantClaim];
   if(typeof tenant!=='string'||!tenant||tenant.length>200||!payload.sub||payload.sub.length>200||typeof payload.scope!=='string'||payload.scope.length>4096)throw new Error('Invalid identity');
   // Issuer-bound namespace prevents collisions if the host later changes provider.
   const principal={tenant:digest([settings.issuer,tenant]),owner:digest([settings.issuer,payload.sub])};
   return {token,clientId:typeof payload.client_id==='string'?payload.client_id:payload.sub,scopes:payload.scope.split(' ').filter(Boolean),expiresAt:payload.exp,resource:new URL(settings.resource),extra:{principal}};
  }catch{throw new OAuthError(OAuthErrorCode.InvalidToken,'Invalid access token');}
 }};
}
