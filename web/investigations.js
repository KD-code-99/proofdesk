"use strict";
let currentCase = null;
let caseBusy = false;

function downloadJSON(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type:"application/json"}));
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

async function caseOperation(operation, message) {
  if (caseBusy) return;
  caseBusy = true;
  document.querySelectorAll("#investigation-panel button, #investigation-panel input, #investigation-panel select, .workflow").forEach(e => e.disabled = true);
  $("activity").textContent = message;
  try { await operation(); }
  catch (error) { $("activity").textContent = error.message + " Your saved work is retained. Use Refresh to resume it."; }
  finally {
    caseBusy = false;
    document.querySelectorAll("#investigation-panel button, #investigation-panel input, #investigation-panel select, .workflow").forEach(e => e.disabled = false);
    document.querySelectorAll('[data-action="replay"], #export-case').forEach(e => e.disabled = !currentCase?.events.length);
  }
}

async function refreshCases() {
  const data = await callTool("list_investigations", {});
  $("saved-cases").replaceChildren(new Option("Choose an investigation", ""));
  for (const item of data.investigations) $("saved-cases").add(new Option(`${item.title} · revision ${item.revision}`, item.id));
  if (currentCase) $("saved-cases").value = currentCase.id;
}

function showCase(doc) {
  currentCase = doc;
  $("case-work").hidden = false;
  $("case-title").textContent = doc.title;
  $("case-revision").textContent = `Saved · revision ${doc.revision}`;
  $("case-problem").textContent = `(${doc.problem.variables.join(", ")}) → (${doc.problem.transitions.join(", ")}) · guess (${doc.problem.numerator}) / (${doc.problem.denominator})`;
  $("case-timeline").replaceChildren();
  for (const event of doc.events) {
    const row = document.createElement("li");
    const button = document.createElement("button");
    const labels = {check:"View conjecture evidence", discover:"View search evidence", trace:"View exact orbit", replay:"View replayed evidence"};
    if (event.status === "REFUTED") labels.check = "View counterexample";
    if (event.status === "CERTIFIED_RATIONAL_INVARIANT") labels.discover = "View conserved quantity";
    button.textContent = `${event.revision}. ${labels[event.action]} · ${event.status.replaceAll("_", " ").toLowerCase()}`;
    button.addEventListener("click", () => caseOperation(async () => {
      const response = await request("/mcp", {jsonrpc:"2.0", id:++mcpSequence, method:"resources/read", params:{uri:`proofdesk://receipts/${event.receipt_id}`}});
      if (response.error) throw Error(response.error.message);
      const receipt = JSON.parse(response.result.contents[0].text);
      display({result:receipt.result, receipt});
      $("activity").textContent = `Viewing evidence from event ${event.revision}. The investigation stays at revision ${doc.revision}.`;
    }, "Loading saved evidence…"));
    row.append(button); $("case-timeline").append(row);
  }
  if (doc.latest) display({result:doc.latest.result, receipt:doc.latest});
  else { $("result").hidden = true; $("empty-state").hidden = true; }
  document.querySelectorAll('[data-action="replay"], #export-case').forEach(e => e.disabled = !doc.events.length);
}

$("new-case").addEventListener("click", () => caseOperation(async () => {
  const preset = $("case-preset").value;
  let args = {};
  if (preset === "rotation") args = {title:"What survives a quarter-turn?", problem:{variables:["x","y"], parameters:[], transitions:["y","-x"], numerator:"x+y", denominator:"1"}};
  if (preset === "custom") args = {title:"My conservation-law investigation", problem:{variables:$("variables").value.split(",").map(v=>v.trim()).filter(Boolean), parameters:$("parameters").value.split(",").map(v=>v.trim()).filter(Boolean), transitions:$("transitions").value.split("\n").map(v=>v.trim()).filter(Boolean), numerator:$("numerator").value, denominator:$("denominator").value}};
  const data = await callTool("start_investigation", args);
  showCase(data.investigation);
  $("search-denominator").value = preset === "rotation" ? "1" : preset === "custom" ? $("denominator").value : "x*y";
  $("orbit-seed").value = data.investigation.problem.variables.map(()=>"1").join(", ");
  await refreshCases();
  $("activity").textContent = "Investigation saved. Challenge the guess, then search for a checked repair.";
}, "Opening an investigation…"));

async function advanceCase(action) {
  return caseOperation(async () => {
    if (!currentCase) throw Error("Begin or resume an investigation first.");
    const args = {investigation_id:currentCase.id, expected_revision:currentCase.revision, action};
    if (action === "discover") Object.assign(args, {search_denominator:$("search-denominator").value, max_degree:Number($("search-degree").value), max_checks:16});
    if (action === "trace") Object.assign(args, {seed:$("orbit-seed").value.split(",").map(v=>v.trim()), steps:Number($("orbit-steps").value)});
    const data = await callTool("advance_investigation", args);
    showCase(data.investigation);
    await refreshCases();
    $("activity").textContent = action === "replay" ? "Replay passed. The stored mathematical evidence reproduced." : action === "discover" && currentCase.active_quantity ? "A quantity was synthesized and independently certified. Explore its orbit or export the full investigation." : "Evidence saved. You can resume this investigation from another MCP client.";
  }, action === "discover" ? "Solving exact coefficient systems and checking candidate formulas…" : "Computing and saving exact evidence…");
}
document.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", () => advanceCase(button.dataset.action)));

$("assistant-form").addEventListener("submit", event => {
  event.preventDefault();
  const text = $("assistant-input").value.trim().toLowerCase();
  const action = /\b(replay|verify|reproduce)\b/.test(text) ? "replay" : /\b(orbit|trace|steps)\b/.test(text) ? "trace" : /\b(find|discover|repair|search)\b/.test(text) ? "discover" : /\b(check|challenge|guess|conjecture)\b/.test(text) ? "check" : null;
  if (!action) { $("activity").textContent = "Try “check the guess”, “find a conserved quantity”, “show the orbit”, or “replay”. This guided simulation supports those four intents."; return; }
  $("assistant-input").value = "";
  advanceCase(action);
});

async function resumeCase(identity) {
  if (!identity) return;
  const data = await callTool("get_investigation", {investigation_id:identity});
  showCase(data.investigation);
  $("search-denominator").value = currentCase.active_quantity?.denominator || currentCase.problem.denominator;
  if (currentCase.problem.variables.join(",") === "x,y,a" && currentCase.problem.denominator === "1") $("search-denominator").value = "x*y";
  $("orbit-seed").value = currentCase.problem.variables.map(()=>"1").join(", ");
  $("activity").textContent = `Resumed revision ${currentCase.revision} from local storage.`;
}
$("saved-cases").addEventListener("change", () => caseOperation(()=>resumeCase($("saved-cases").value), "Resuming saved investigation…"));
$("refresh-cases").addEventListener("click", () => caseOperation(async () => { await refreshCases(); if (currentCase) await resumeCase(currentCase.id); }, "Refreshing saved work…"));
$("export-case").addEventListener("click", () => caseOperation(async () => {
  const data = await callTool("export_investigation", {investigation_id:currentCase.id});
  downloadJSON(data.bundle, `proofdesk-investigation-${currentCase.id}.json`);
  $("activity").textContent = "Exported the event history, all evidence receipts, and the bundle digest. Audit it here or with the offline command.";
}, "Collecting portable evidence…"));
$("audit-bundle").addEventListener("change", event => {
  const file = event.target.files[0];
  if (!file) return;
  caseOperation(async () => {
    if (file.size > 4*1024*1024 - 100) throw Error("Choose an investigation bundle smaller than 4 MiB.");
    const response = await request("/api/audit-bundle", {bundle:JSON.parse(await file.text())});
    $("activity").textContent = `Bundle replay passed: ${response.receipts_replayed} receipts reproduced across ${response.events} events. This checks content and mathematics, not authorship.`;
  }, "Recomputing every bundled receipt…");
  event.target.value = "";
});

function renderExploration(result) {
  const extra = document.createElement("div"); extra.className = "exploration-detail";
  if (result.search) {
    const details = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = "See how counterexamples guided the search";
    const list = document.createElement("ol");
    for (const attempt of result.search.attempts) {
      const row = document.createElement("li");
      const formula = document.createElement("code"); formula.textContent = `(${attempt.numerator}) / (${attempt.denominator})`;
      const outcome = document.createElement("p"); outcome.textContent = attempt.counterexample ? "Rejected at " + Object.entries(attempt.counterexample).map(([k,v])=>`${k}=${v}`).join(", ") : attempt.status.replaceAll("_", " ");
      row.append(formula, outcome); list.append(row);
    }
    details.append(summary, list); extra.append(details);
  }
  if (result.rows?.length) {
    const heading = document.createElement("h3"); heading.textContent = "Watch the quantity through exact steps";
    const label = document.createElement("label"); label.textContent = "Inspect orbit step";
    const slider = document.createElement("input"); slider.type = "range"; slider.min = 0; slider.max = result.rows.length-1; slider.value = 0;
    const readout = document.createElement("p"); readout.className = "orbit-readout";
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 600 150"); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "Quantity versus orbit step, displayed approximately. Exact values follow in the table."); svg.classList.add("orbit-plot");
    const numbers = result.rows.map(row=>{const [a,b="1"]=row.quantity.split("/");return Number(a)/Number(b);});
    const low = Math.min(...numbers), high = Math.max(...numbers), span = high-low || 1;
    const positions = numbers.map((v,i)=>[24+i*552/Math.max(1,numbers.length-1), high === low ? 75 : 126-(v-low)/span*102]);
    const line = document.createElementNS(svg.namespaceURI,"polyline"); line.setAttribute("points",positions.map(p=>p.join(",")).join(" ")); svg.append(line);
    const dot = document.createElementNS(svg.namespaceURI,"circle"); dot.setAttribute("r","6"); svg.append(dot);
    const update = () => {
      const row=result.rows[Number(slider.value)], [x,y]=positions[Number(slider.value)];
      dot.setAttribute("cx",x);dot.setAttribute("cy",y);
      readout.textContent = `Step ${row.step} · ${Object.entries(row.state).map(([k,v])=>`${k}=${v}`).join(", ")} · quantity=${row.quantity}`;
    };
    slider.addEventListener("input",update);update();label.append(slider);
    const scroll = document.createElement("div"); scroll.className="orbit-table"; scroll.tabIndex=0; scroll.setAttribute("role","region"); scroll.setAttribute("aria-label","Exact orbit values");
    const table=document.createElement("table"), caption=document.createElement("caption");caption.textContent="Exact rational values; the plot is a visual approximation.";table.append(caption);
    const head=document.createElement("thead"), header=document.createElement("tr");
    for(const text of ["Step",...result.variables,"Quantity"]){const th=document.createElement("th");th.scope="col";th.textContent=text;header.append(th);}head.append(header);table.append(head);
    const body=document.createElement("tbody");
    for(const row of result.rows){const tr=document.createElement("tr");for(const value of [row.step,...result.variables.map(v=>row.state[v]),row.quantity]){const td=document.createElement("td");td.textContent=value;tr.append(td);}body.append(tr);}table.append(body);scroll.append(table);
    extra.append(heading,svg,label,readout,scroll);
  }
  if (extra.childNodes.length) $("result-detail").after(extra);
}

caseOperation(async () => { await refreshCases(); $("activity").textContent = "Ready. Begin an investigation or resume saved work."; }, "Connecting to the local MCP tool catalog…");
