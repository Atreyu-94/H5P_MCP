import {execute} from '../application/execute.js';
import {limit} from '../domain/limits.js';
import type {CoreRequest,Native} from '../domain/types.js';
let size=0;const chunks:Buffer[]=[];
try {
 for await(const chunk of process.stdin) {
  size+=chunk.length;
  if(size>limit('JSON_BYTES',16777216)) throw Object.assign(new Error('Input budget exceeded'),{code:'INPUT_TOO_LARGE'});
  chunks.push(chunk);
 }
 const result=await execute(JSON.parse(Buffer.concat(chunks).toString('utf8')) as CoreRequest);
 const response=JSON.stringify({ok:true,result});
 if(Buffer.byteLength(response)>limit('OUTPUT_BYTES',33554432)) throw Object.assign(new Error('Output budget exceeded'),{code:'OUTPUT_TOO_LARGE'});
 process.stdout.write(response);
} catch(error) {
 const failure=error as Native;
 process.stdout.write(JSON.stringify({ok:false,code:failure.code||'BACKEND_ERROR',errors:[failure.message],details:failure.details}));
 process.exitCode=1;
}
