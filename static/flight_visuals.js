(function(root){'use strict';
// Decorative local-clock scene, not a solar/lunar ephemeris or flight heading.
function clockScene(date=new Date(),override){
 const hour=date.getHours()+date.getMinutes()/60+date.getSeconds()/3600,day=hour>=6&&hour<18;
 const start=new Date(date);start.setHours(day?6:18,0,0,0);if(!day&&hour<6)start.setDate(start.getDate()-1);
 const automatic=day?'light':'dark';return {theme:override||automatic,automatic,period:String(start.getTime()),progress:((hour-(day?6:18)+24)%24)/12};
}
function bearingTo(origin,target){
 const lat=p=>p?.lat??p?.latitude,lng=p=>p?.lng??p?.longitude;
 const a=lat(origin),b=lng(origin),c=lat(target),d=lng(target);
 if(![a,b,c,d].every(v=>typeof v==='number'&&Number.isFinite(v))||(a===c&&b===d))return 0;
 const rad=Math.PI/180,delta=(d-b)*rad;
 return (Math.atan2(Math.sin(delta)*Math.cos(c*rad),Math.cos(a*rad)*Math.sin(c*rad)-Math.sin(a*rad)*Math.cos(c*rad)*Math.cos(delta))/rad+360)%360;
}
function helicopterIcon(angle=0){return '<svg class="helicopter-position" viewBox="-12 -8 72 72" role="img" aria-label="Helicopter position"><g transform="rotate('+angle+' 24 28)"><path class="position-hull" d="M24 7c-8 0-10 10-9 19l5 12 2 18h4l2-18 5-12c1-9-1-19-9-19Z"/><path fill="#163c42" d="M18 14q6-6 12 0l1 9-7-2-7 2Z"/><path class="position-skids" d="M12 23v17m24-17v17M12 29h24M17 53h14"/><path class="position-blades" d="M5 25h38v5H5zM21.5 8h5v39h-5z"/><circle cx="24" cy="27.5" r="4" fill="#183f32"/></g></svg>';}
function rotorSvg(){return '<svg class="rotor-aircraft" viewBox="0 0 80 100" aria-hidden="true"><path class="loader-fuselage" d="M40 10c-11 0-15 17-12 32l7 18 2 26h6l2-26 7-18c3-15-1-32-12-32Z"/><path class="loader-cockpit" d="M32 20q8-8 16 0l2 12-10-3-10 3Z"/><path class="loader-skids" d="M21 33v26m38-26v26M21 43h38M30 82h20"/><g class="loader-blades"><rect x="4" y="31" width="72" height="7" rx="3"/><rect x="36.5" y="0" width="7" height="69" rx="3"/><circle cx="40" cy="34.5" r="8" class="loader-hub"/></g></svg>';}
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function regionList(features,available){return features.map((f,i)=>{const p=f.properties||{},id=p.region_id||p.id,ready=Boolean(available(id==='bhadra_reserve'?'bhadra':id));return '<button class="region-option '+(ready?'region-ready':'region-planned')+'" data-region-index="'+i+'"'+(ready?'':' disabled aria-disabled="true"')+'><span>'+escape(p.name||id||'Region')+'</span><small>'+ (ready?'Available · Explore →':'Planned')+'</small></button>';}).join('');}
function installScene(){
 const doc=root.document,button=doc.getElementById('theme-toggle'),art=doc.querySelector('.hero-art');let override=null;
 try{override=JSON.parse(root.localStorage.getItem('helps-theme-clock-override'));}catch{}
 function update(){
  const date=new Date(),clock=clockScene(date);if(override?.period!==clock.period)override=null;
  const theme=override?.theme||clock.theme;doc.body.dataset.theme=theme;
  button.setAttribute('aria-label','Switch to '+(theme==='dark'?'light':'dark')+' theme');button.title='Automatic local-clock theme: day 06:00–18:00. Manual choice lasts until the next day/night period.';
  button.querySelector('span').textContent=theme==='dark'?'Lights on':'Lights off';
  if(!art)return;
  const x=8+84*clock.progress,y=9+24*(1-Math.sin(Math.PI*clock.progress)),box=art.getBoundingClientRect();
  if(!box.width||!box.height)return;
  const dx=(x-50)*box.width/100,dy=(y-50)*box.height/100;
  art.style.setProperty('--celestial-x',x+'%');art.style.setProperty('--celestial-y',y+'%');
  art.style.setProperty('--heli-heading',(Math.atan2(dy,dx)*180/Math.PI+90)+'deg');
  art.style.setProperty('--beam-angle',(Math.atan2(-dy,-dx)*180/Math.PI)+'deg');art.style.setProperty('--beam-length',Math.hypot(dx,dy)+'px');
  const orb=doc.getElementById('celestial-orb');if(orb){orb.className='celestial-orb '+(theme==='light'?'sun':'moon');orb.setAttribute('aria-label',theme==='light'?'Sun illustration':'Full moon illustration');}
  const label=doc.getElementById('scene-clock');if(label)label.textContent=date.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+' · device local time';
 }
 button.onclick=()=>{const clock=clockScene();override={theme:doc.body.dataset.theme==='dark'?'light':'dark',period:clock.period};try{root.localStorage.setItem('helps-theme-clock-override',JSON.stringify(override));}catch{}update();};
 const onTab=e=>{if(e.detail==='overview')root.requestAnimationFrame(update);};root.addEventListener('helps:tab',onTab);
 update();const timer=root.setInterval(update,60000);root.addEventListener('resize',update);doc.addEventListener('visibilitychange',update);
 return {update,dispose(){root.clearInterval(timer);root.removeEventListener('helps:tab',onTab);root.removeEventListener('resize',update);doc.removeEventListener('visibilitychange',update);}};
}
const api={clockScene,bearingTo,helicopterIcon,rotorSvg,regionList,installScene};if(typeof module!=='undefined')module.exports=api;else root.HELPSVisuals=api;
})(typeof window==='undefined'?globalThis:window);
