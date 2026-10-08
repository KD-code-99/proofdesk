"use strict";
let mode = "invariant";
let lastReceipt = null;
const $ = id => document.getElementById(id);
const copy = {
  invariant: ["Find what stays constant.", "The Lyness map changes x and y. We can check whether a proposed quantity survives every step.", "Check the statement"],
  recurrence: ["Skip the waiting. Keep the exact answer.", "These recurrences have structure we can use. Compute a future state without simulating every intermediate step.", "Compute the future state"],
  inequality: ["A sharp bound needs a witness.", "A sum-of-squares identity proves the bound. An admissible equality witness shows why the constant cannot increase.", "Inspect the certificate"]
};
document.querySelectorAll(".workflow").forEach(button => button.addEventListener("click", () => {
  mode = button.dataset.mode;
  document.querySelectorAll(".workflow").forEach(b => b.classList.toggle("active", b === button));
  for (const name of Object.keys(copy)) $(name + "-fields").hidden = name !== mode;
  $("question-title").textContent = copy[mode][0];
  $("question-description").textContent = copy[mode][1];
  $("run").replaceChildren(document.createTextNode(copy[mode][2] + " ↗"));
  $("result").hidden = true; $("empty-state").hidden = false; $("activity").textContent = "";
}));
$("valid-preset").addEventListener("click", () => { $("numerator").value = "(x+1)*(y+1)*(x+y+a)"; $("denominator").value = "x*y"; });
$("invalid-preset").addEventListener("click", () => { $("numerator").value = "x+y"; $("denominator").value = "1"; });
async function request(path, body) {
  const response = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json","Accept":"application/json, text/event-stream",...(path==='/mcp'?{'MCP-Protocol-Version':'2025-11-25'}:{})}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The check could not finish");
  return data;
}
let mcpSequence=0;
const mcpReady=request('/mcp',{jsonrpc:'2.0',id:++mcpSequence,method:'initialize',params:{protocolVersion:'2025-11-25',capabilities:{},clientInfo:{name:'proofdesk-demo',version:'0.1.0'}}}).then(async response=>{
  if(response.error)throw Error(response.error.message);
  await fetch('/mcp',{method:'POST',headers:{'Content-Type':'application/json','MCP-Protocol-Version':'2025-11-25'},body:JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized'})});
});
mcpReady.catch(()=>{});
async function callTool(tool,args){
  await mcpReady;
  const response=await request('/mcp',{jsonrpc:'2.0',id:++mcpSequence,method:'tools/call',params:{name:tool,arguments:args}});
  if(response.error)throw Error(response.error.message);
  if(response.result.isError)throw Error(response.result.content[0].text);
  return response.result.structuredContent;
}
function display(data) {
  const r = data.result; lastReceipt = data.receipt;
  $("result").hidden = false; $("empty-state").hidden = true;
  $("evidence-type").textContent = r.evidence_type.replaceAll("_", " ").toUpperCase();
  const titles = {CERTIFIED_RATIONAL_INVARIANT:"The quantity is conserved.", REFUTED:"This guess changes.", TRIVIAL_PARAMETER_FUNCTION:"Only the fixed parameter survives.", EXACT_RECURRENCE_RESULT:"The future state is ready.", CERTIFIED_SHARP_INEQUALITY:"The bound is proved and attained.", INVALID_CERTIFICATE:"This certificate does not prove the bound."};
  $("result-heading").textContent = titles[r.status] || "The checker returned a scoped result.";
  $("status-pill").textContent = r.status.startsWith("CERTIFIED") ? "✓ CHECKED" : r.status === "REFUTED" ? "× REFUTED" : r.status === "EXACT_RECURRENCE_RESULT" ? "✓ EXACT" : "REVIEW";
  $("status-pill").className = "status-pill" + (r.status === "REFUTED" ? " refuted" : r.status === "INVALID_CERTIFICATE" || r.status === "TRIVIAL_PARAMETER_FUNCTION" ? " unknown" : "");
  $("explanation").textContent = r.explanation;
  $("result-detail").textContent = r.counterexample ? "Counterexample: " + Object.entries(r.counterexample).map(([k,v]) => `${k} = ${v}`).join(", ") : r.value ? "Result = " + r.value : r.formula;
  $("certificate").textContent = JSON.stringify({domain:r.domain, verification:r.verification, certificate:r.certificate}, null, 2);
  $("receipt-id").textContent = lastReceipt.receipt_id;
  $("result-scope").textContent = r.scope;
}
$("math-form").addEventListener("submit", async event => {
  event.preventDefault(); $("run").disabled = true;
  $("activity").textContent = "Reconstructing the obligation and checking it independently…";
  let tool, args;
  if (mode === "invariant") {
    tool = "check_invariant";
    args = {variables:$("variables").value.split(",").map(x=>x.trim()).filter(Boolean), parameters:$("parameters").value.split(",").map(x=>x.trim()).filter(Boolean), transitions:$("transitions").value.split("\n").map(x=>x.trim()).filter(Boolean), numerator:$("numerator").value, denominator:$("denominator").value};
  } else if (mode === "recurrence") { tool = "recurrence_jump"; args = {family:$("family").value, steps:$("steps").value, modulus:$("modulus").value}; }
  else { tool = "check_inequality"; args = {bound:$("bound").value}; }
  try { display(await callTool(tool,args)); $("activity").textContent = "Check complete. The receipt binds the input, result, and engine hashes."; }
  catch (error) { $("activity").textContent = error.message; }
  finally { $("run").disabled = false; }
});
$("replay").addEventListener("click", async () => {
  $("replay").disabled = true;
  try { const r = await request("/api/replay", {receipt:lastReceipt}); $("activity").textContent = r.status === "REPLAY_PASSED" ? "Replay passed: the same inputs reproduced the mathematical result." : "Replay did not pass."; }
  catch (error) { $("activity").textContent = error.message; }
  finally { $("replay").disabled = false; }
});
$("download").addEventListener("click", () => {
  if (!lastReceipt) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastReceipt, null, 2)], {type:"application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = "proofdesk-" + lastReceipt.receipt_id.slice(0,12) + ".json"; link.click(); URL.revokeObjectURL(url);
});
