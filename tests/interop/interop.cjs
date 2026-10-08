const {Client,StreamableHTTPClientTransport}=require('@modelcontextprotocol/client');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');const {spawn}=require('node:child_process');
const root=path.resolve(__dirname,'../..');const folder=root;const rows=[];
const child=spawn(process.env.PYTHON||'python',['-B','-m','proofdesk','--port','0'],{cwd:folder,windowsHide:true,stdio:['ignore','pipe','pipe']});
const endpoint=new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('App did not listen')),45000);child.stdout.on('data',data=>{raw+=data;const m=raw.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0]+'/mcp');}});child.on('exit',code=>{if(code)reject(Error('App exited: '+code));});});
async function main(){try{const url=await endpoint;for(const mode of ['legacy','auto']){
const client=new Client({name:'official-sdk-interop',version:'0.1.0'},{versionNegotiation:{mode}});const transport=new StreamableHTTPClientTransport(new URL(url));
try{await client.connect(transport);assert.equal(client.getServerVersion().name,'proofdesk');assert.equal(client.getProtocolEra(),'legacy');const {tools}=await client.listTools();assert.deepEqual(tools.map(t=>t.name).sort(),['check_inequality','check_invariant','recurrence_jump']);
const cases=[['check_invariant',{numerator:'x+y',denominator:'1'},'REFUTED'],['check_invariant',{numerator:'(x+1)*(y+1)*(x+y+a)',denominator:'x*y'},'CERTIFIED_RATIONAL_INVARIANT'],['recurrence_jump',{family:'fibonacci',steps:'1000000000000000000000000000000',modulus:'1000000007'},'EXACT_RECURRENCE_RESULT'],['check_inequality',{bound:'2'},'CERTIFIED_SHARP_INEQUALITY']];
for(const [name,arguments,status] of cases){const result=await client.callTool({name,arguments});assert.equal(result.isError,false);assert.equal(result.structuredContent.result.status,status);assert.match(result.structuredContent.receipt.receipt_id,/^[a-f0-9]{64}$/);}
let unknownRejected=false;try{await client.callTool({name:'unknown_mathematical_tool',arguments:{}});}catch{unknownRejected=true;}assert.ok(unknownRejected,'Unknown tool names must be protocol-level errors');
rows.push({client_mode:mode,negotiated_era:client.getProtocolEra(),catalog_tools:tools.length,actual_tool_results:cases.map(r=>r[2]),unknown_tool_protocol_error:unknownRejected});
}finally{await transport.terminateSession();await client.close();}}
const pkg=JSON.parse(fs.readFileSync(path.join(__dirname,'node_modules/@modelcontextprotocol/client/package.json'),'utf8'));const report={status:'PASS',checked_at:new Date().toISOString(),sdk:pkg.name,version:pkg.version,tests:rows,scope:'Executed official SDK default and automatic negotiation, catalog and mathematical tool calls against owned localhost. This is interoperability evidence, not official certification or live Alexa access.'};fs.writeFileSync(path.join(folder,'evidence/official-sdk-interop.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{child.kill();}}
main().catch(error=>{console.error(error);process.exitCode=1;});
