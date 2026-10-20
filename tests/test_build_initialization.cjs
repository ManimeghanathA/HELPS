const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(){
 const nodes=new Map();
 function node(id){if(!nodes.has(id))nodes.set(id,{value:id==='build-region'?'bhadra':id==='build-mode'?'date_only':'',textContent:'',disabled:false,checked:false,buttons:[],setAttribute(){},removeAttribute(){},append(){},replaceChildren(){},scrollIntoView(){this.scrolled=true;},focus(){this.focused=true;},querySelectorAll(selector){return selector==='[data-day]'?this.buttons:[];},set innerHTML(value){this.html=value;if(id==='build-search-results')this.buttons=[...value.matchAll(/data-day="([^"]+)" data-historical="([^"]+)"/g)].map(m=>({dataset:{day:m[1],historical:m[2]},disabled:false}));},get innerHTML(){return this.html||'';}});return nodes.get(id);}
 let resolveWorkflow,rejectWorkflow;const workflow=new Promise((resolve,reject)=>{resolveWorkflow=resolve;rejectWorkflow=reject;});
 const H={ready:Promise.resolve(),esc:String,requestGate:require('../static/unified_core.js').requestGate,api:async url=>url.includes('/regions')?{regions:[{region_id:'bhadra',name:'Bhadra'}]}:url.includes('/workflow')?workflow:url.includes('/credentials')?{credentials:{}}:url.includes('/jobs?')?{jobs:[]}:url.includes('/imagery-search/')?{status:'completed',errors:[],months:[{month:'2026-10',recommended_date:'2026-10-12',observations:[{date:'2026-10-12'}]}]}:{},post:async()=>({search_id:'search'})};
 const context={HELPS:H,document:{getElementById:node,createElement:()=>node('created')},Event:class{},setTimeout,Date,console};vm.createContext(context);vm.runInContext(fs.readFileSync('static/unified_build.js','utf8'),context);
 return {node,resolve:()=>resolveWorkflow({region_id:'bhadra',minimum_new_date:'2026-06-02',current_date:null,sources:[],versions:[],history:[]}),reject:rejectWorkflow};
}
test('build controls wait for chronology and date selection brings processing into view',async()=>{
 const h=harness();await flush();assert.equal(h.node('build-search').disabled,true);assert.equal(h.node('build-start').disabled,true);
 h.resolve();await flush();assert.equal(h.node('build-search').disabled,false);
 await h.node('build-search').onclick();const button=h.node('build-search-results').buttons[0];assert.ok(button);await button.onclick();
 assert.equal(h.node('build-date').value,'2026-10-12');assert.equal(h.node('build-form').scrolled,true);assert.doesNotMatch(h.node('build-progress').textContent,/null|Cannot read/);
});
test('workflow initialization errors are visible and cannot bypass date rules',async()=>{
 const h=harness();await flush();h.reject(Error('Workflow unavailable for test'));await flush();
 assert.match(h.node('build-progress').textContent,/Workflow unavailable for test/);assert.equal(h.node('build-start').disabled,true);assert.equal(h.node('build-search').disabled,true);
});
