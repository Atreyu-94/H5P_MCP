"""B0 subprocess protocol, termination and bounded stream stress on both runtimes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

parser=argparse.ArgumentParser()
parser.add_argument('--runtime-report',type=Path,required=True)
parser.add_argument('--bun',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[2]
reference=json.loads(args.runtime_report.read_text())
root=Path(tempfile.mkdtemp(prefix='h5p-b0-process-'))
env=dict(os.environ,H5P_MCP_LUMI_RUNTIME=reference['npm_runtime'],TMP=str(root),TEMP=str(root),TMPDIR=str(root))
bridge=str(repo/'h5p_mcp/lumi/bridge.cjs')
report={'checks':{},'artifacts':str(root),'memory_note':'RSS includes native/runtime allocations; samples are not proof of absence of leaks.'}
stress=r'''
const assert=require('node:assert/strict');
const {Readable,Writable}=require('node:stream');
const {pipeline}=require('node:stream/promises');
(async()=>{
 const samples=[];
 for(let run=0;run<30;run++){
   let bytes=0;
   const chunk=Buffer.alloc(65536,42);
   await pipeline(Readable.from(Array(16).fill(chunk)),new Writable({highWaterMark:1024,
     write(data,encoding,done){bytes+=data.length;setImmediate(done);}}));
   assert.equal(bytes,1048576);
   samples.push(process.memoryUsage());
 }
 await assert.rejects(pipeline(Readable.from(['x']),new Writable({write(c,e,done){done(new Error('controlled stream failure'));}})),/controlled stream failure/);
 console.log(JSON.stringify({backpressure:'passed',stream_error:'passed',iterations:30,memory:samples}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
for label,exe in [('node',shutil.which('node')),('bun',args.bun)]:
    checks={}
    for name,payload,code,extra in [
        ('empty_eof',b'','BACKEND_ERROR',{}),
        ('oversized_input',b'x'*1024,'INPUT_TOO_LARGE',{'H5P_MCP_MAX_JSON_BYTES':'64'}),
    ]:
        result=subprocess.run([exe,bridge],input=payload,capture_output=True,env={**env,**extra},timeout=20)
        assert result.returncode!=0
        assert json.loads(result.stdout)['code']==code
        checks[name]='passed'
    process=subprocess.Popen([exe,bridge],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    try:
        time.sleep(0.3)
        assert process.poll() is None, 'Must wait for stdin EOF'
        process.terminate()
        process.communicate(timeout=10)
        checks['termination_and_reap']='passed'
    finally:
        if process.poll() is None: process.kill()
        process.communicate()
    timings=[]
    for _ in range(10):
        start=time.monotonic()
        result=subprocess.run([exe,bridge],input=json.dumps({'action':'catalog','data_dir':str(root/label)}).encode(),capture_output=True,env=env,timeout=20)
        assert result.returncode==0, result.stderr
        assert json.loads(result.stdout)['libraries']=={}
        assert not list(root.glob('h5p-lumi-*')), 'Job temporary directory leaked'
        timings.append(time.monotonic()-start)
    checks['repeated_stdio_and_cleanup']={'status':'passed','seconds':timings,'iterations':10}
    result=subprocess.run([exe,'-e',stress],capture_output=True,text=True,env=env,timeout=30)
    assert result.returncode==0,result.stderr
    checks['stream_stress']=json.loads(result.stdout)
    report['checks'][label]=checks
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps({'report':str(args.output),'status':'passed'}))
