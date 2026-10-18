/* Navigation bridge for the archived export and maintained Flask app. */
(() => {
 'use strict';
 document.addEventListener('click',event=>{
  const a=event.target.closest&&event.target.closest('a[href]');if(!a)return;
  const u=new URL(a.href,location.href);
  if(u.hash==='#setup-required'||/noryx\.example$/.test(u.hostname)){
   event.preventDefault();event.stopImmediatePropagation();location.assign('/client/tickets');return;
  }
  if(u.origin===location.origin&&!a.download&&!event.metaKey&&!event.ctrlKey&&!event.shiftKey&&!event.altKey&&event.button===0&&(!a.target||a.target==='_self')&&(u.pathname!==location.pathname||u.pathname.startsWith('/client/'))){event.preventDefault();event.stopImmediatePropagation();location.assign(u.href);}
 },true);
 document.addEventListener('submit',event=>{if(location.pathname.startsWith('/reseller/apply')){event.preventDefault();event.stopImmediatePropagation();location.assign('/client/tickets');}},true);
 const originalFetch=window.fetch.bind(window);
 window.fetch=(input,init)=>{
  const u=new URL(typeof input==='string'?input:input instanceof URL?input.href:input.url,location.href);
  if(u.origin===location.origin&&u.pathname==='/scripts/fetch-currency-rates.php')return Promise.resolve(new Response('{}',{status:200,headers:{'Content-Type':'application/json'}}));
  return originalFetch(input,init);
 };
})();
