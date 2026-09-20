export class Pool {
 private active=0;
 private queue:Array<()=>void>=[];
 constructor(readonly capacity=2,readonly waiting=8) {
  if(!Number.isSafeInteger(capacity)||capacity<1||!Number.isSafeInteger(waiting)||waiting<0) throw new Error('Invalid pool limits');
 }
 async run<T>(work:()=>Promise<T>,signal:AbortSignal):Promise<T> {
  signal.throwIfAborted();
  if(this.active>=this.capacity) {
   if(this.queue.length>=this.waiting) throw Object.assign(new Error('Queue full'),{code:'LIMIT_EXCEEDED'});
   await new Promise<void>((resolve,reject)=>{
    const start=()=>{signal.removeEventListener('abort',abort);resolve();};
    const abort=()=>{this.queue=this.queue.filter(item=>item!==start);reject(signal.reason);};
    this.queue.push(start);signal.addEventListener('abort',abort,{once:true});
   });
  } else this.active++;
  try {signal.throwIfAborted();return await work();}
  finally {const next=this.queue.shift();if(next) next();else this.active--;}
 }
 get running(){return this.active;}
 get queued(){return this.queue.length;}
}
