import {Pool} from '../infrastructure/pool.js';
import type {Principal} from '../storage/objects.js';
export class Busy extends Error {}
/** Process-wide limits; one process owns this store until a distributed scheduler exists. */
export class Admission {
 readonly pool=new Pool(2,8);
 private users=new Map<string,number>();private tenants=new Map<string,number>();
 private rates=new Map<string,{count:number;until:number}>();
 async run<T>(principal:Principal,signal:AbortSignal,work:()=>Promise<T>):Promise<T> {
  const user=principal.tenant+':'+principal.owner,now=Date.now();
  for(const [key,bucket] of this.rates)if(bucket.until<=now)this.rates.delete(key);
  const rate=this.rates.get(principal.tenant)||{count:0,until:now+60000};
  if(rate.count>=120||this.rates.size>=1024&&!this.rates.has(principal.tenant)||(this.users.get(user)||0)>=2||(this.tenants.get(principal.tenant)||0)>=4)throw new Busy();
  rate.count++;this.rates.set(principal.tenant,rate);
  this.users.set(user,(this.users.get(user)||0)+1);this.tenants.set(principal.tenant,(this.tenants.get(principal.tenant)||0)+1);
  try{return await this.pool.run(work,signal);}
  catch(error){if((error as {code?:string}).code==='LIMIT_EXCEEDED')throw new Busy();throw error;}
  finally{
   for(const [map,key] of [[this.users,user],[this.tenants,principal.tenant]] as const){const remaining=map.get(key)!-1;if(remaining)map.set(key,remaining);else map.delete(key);}
  }
 }
}
