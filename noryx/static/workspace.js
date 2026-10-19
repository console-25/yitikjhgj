'use strict';
(() => {
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(window.anime&&!reduced){
    anime({targets:'.page-heading, .auth-intro, .auth-card, .app-main > .card, .stat-card',translateY:[8,0],opacity:[.65,1],duration:420,delay:anime.stagger(35),easing:'easeOutCubic'});
    document.querySelectorAll('.chart-line').forEach(line=>anime({targets:line,strokeDashoffset:[anime.setDashoffset,0],duration:850,easing:'easeOutCubic'}));
  }
  document.addEventListener('click',event=>{
    const open=event.target.closest('[data-open-dialog]');
    if(open)document.getElementById(open.dataset.openDialog)?.showModal();
    if(event.target.closest('[data-close-dialog]'))event.target.closest('dialog')?.close();
    document.querySelectorAll('.popover[open]').forEach(item=>{if(!item.contains(event.target))item.open=false;});
  });
  const search=document.querySelector('[data-workspace-search]');
  const results=document.querySelector('[data-search-results]');
  function searchPages(){
    if(!results)return;
    results.replaceChildren();
    const links=[...document.querySelectorAll('.sidebar nav a')].filter(link=>link.textContent.toLowerCase().includes(search.value.toLowerCase()));
    links.forEach(link=>{const clone=document.createElement('a');clone.href=link.href;clone.className='search-result';clone.textContent=link.textContent.trim();results.append(clone);});
    if(!links.length)results.textContent='No matching pages.';
  }
  search?.addEventListener('input',searchPages);searchPages();
  document.addEventListener('keydown',event=>{
    if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'&&search){event.preventDefault();const dialog=search.closest('dialog');if(!dialog.open)dialog.showModal();search.focus();}
    if(event.key==='Tab'&&document.body.classList.contains('menu-open')){
      const items=[...document.querySelectorAll('#app-sidebar a, #app-sidebar button')].filter(item=>item.getClientRects().length);
      const first=items[0],last=items.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
    }
  });
  const approved=new WeakSet();
  const confirmation=document.querySelector('#confirm-dialog');let pending=null;
  document.addEventListener('submit',event=>{
    const form=event.target,button=event.submitter;
    const message=button?.dataset.confirm||form.dataset.confirm;
    if(!message||approved.has(form)){approved.delete(form);return;}
    event.preventDefault();event.stopImmediatePropagation();pending={form,button};
    confirmation.querySelector('[data-confirm-message]').textContent=message;confirmation.showModal();
  },true);
  confirmation?.querySelector('[data-confirm-cancel]').addEventListener('click',()=>{pending=null;confirmation.close();});
  confirmation?.querySelector('[data-confirm-accept]').addEventListener('click',()=>{const action=pending;pending=null;confirmation.close();if(action){approved.add(action.form);action.form.requestSubmit(action.button);}});
  document.querySelectorAll('[data-auto-submit]').forEach(input=>input.addEventListener('change',()=>input.form.requestSubmit()));
  document.querySelectorAll('table[data-data-table]').forEach(table=>{
    const rows=[...table.tBodies[0].rows];let page=0,ascending=true,filtered=rows;
    const toolbar=document.createElement('div');toolbar.className='table-toolbar';
    const label=document.createElement('label');label.textContent='Search records';const input=document.createElement('input');input.type='search';input.placeholder='Filter this table';label.append(input);toolbar.append(label);
    const pagination=document.createElement('div');pagination.className='table-pagination';
    const previous=document.createElement('button'),next=document.createElement('button'),info=document.createElement('span');previous.type=next.type='button';previous.textContent='← Previous';next.textContent='Next →';pagination.append(previous,info,next);
    const container=table.closest('.table-wrap')||table;container.before(toolbar);container.after(pagination);
    function render(){rows.forEach(row=>row.hidden=true);const pages=Math.max(1,Math.ceil(filtered.length/12));page=Math.min(page,pages-1);filtered.slice(page*12,page*12+12).forEach(row=>{row.hidden=false;table.tBodies[0].append(row);});info.textContent=`${filtered.length} records · Page ${page+1} of ${pages}`;previous.disabled=page===0;next.disabled=page===pages-1;}
    input.addEventListener('input',()=>{filtered=rows.filter(row=>row.textContent.toLowerCase().includes(input.value.toLowerCase()));page=0;render();});
    previous.addEventListener('click',()=>{page--;render();});next.addEventListener('click',()=>{page++;render();});
    [...table.tHead.rows[0].cells].forEach((cell,index)=>{const button=document.createElement('button');button.type='button';button.className='table-sort';button.textContent=cell.textContent+' ↕';cell.replaceChildren(button);button.addEventListener('click',()=>{filtered.sort((a,b)=>a.cells[index].textContent.localeCompare(b.cells[index].textContent,undefined,{numeric:true})*(ascending?1:-1));ascending=!ascending;page=0;render();});});render();
  });
  document.querySelectorAll('[data-plan-wizard]').forEach(form=>{
    const json=form.elements.specifications;
    form.querySelectorAll('[data-resource]').forEach(input=>input.addEventListener('input',()=>{try{const value=JSON.parse(json.value);if(!value||Array.isArray(value)||typeof value!=='object')throw Error();if(input.value)value[input.dataset.resource]=input.value;else delete value[input.dataset.resource];json.value=JSON.stringify(value,null,2);json.setCustomValidity('');}catch{json.setCustomValidity('Enter a valid JSON object before changing resource fields.');}}));
    json?.addEventListener('input',()=>{try{const value=JSON.parse(json.value);if(!value||Array.isArray(value)||typeof value!=='object')throw Error();json.setCustomValidity('');form.querySelectorAll('[data-resource]').forEach(input=>input.value=value[input.dataset.resource]||'');}catch{json.setCustomValidity('Enter a valid JSON object.');}});
    const prices=[...form.querySelectorAll('[data-price-cycle]')];
    function loadPrice(cycle){const price=prices.find(p=>p.dataset.priceCycle===cycle);if(price){for(const name of ['amount','currency','setup_fee'])form.elements[name].value=price.dataset[name==='setup_fee'?'setup':name];}else{form.elements.amount.value=0;form.elements.setup_fee.value=0;}}
    form.elements.cycle?.addEventListener('change',()=>loadPrice(form.elements.cycle.value));
    prices.forEach(button=>button.addEventListener('click',()=>{form.elements.cycle.value=button.dataset.priceCycle;loadPrice(button.dataset.priceCycle);}));
    form.querySelector('[data-edit-existing]')?.addEventListener('click',()=>{const select=form.querySelector('[data-existing-plan]');if(select.value)location.assign('/admin/plans/'+encodeURIComponent(select.value));else {select.setCustomValidity('Select a saved plan to edit.');select.reportValidity();select.setCustomValidity('');}});
  });
  document.addEventListener('click',async event=>{
    const link=event.target.closest('[data-order-drawer]');if(!link||event.ctrlKey||event.metaKey||event.shiftKey||event.button!==0)return;
    event.preventDefault();
    try{
      const response=await fetch(link.href,{credentials:'same-origin'});if(!response.ok||response.redirected)throw Error();
      const parsed=new DOMParser().parseFromString(await response.text(),'text/html');const content=parsed.querySelector('#main-content');if(!content)throw Error();
      const dialog=document.createElement('dialog');dialog.className='workspace-dialog order-drawer';const close=document.createElement('button');close.type='button';close.textContent='Close ×';close.dataset.closeDialog='';dialog.append(close);
      content.querySelector('footer')?.remove();dialog.append(...content.childNodes);document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove(),{once:true});dialog.showModal();
    }catch{location.assign(link.href);}
  });
  window.addEventListener('pageshow',()=>document.querySelectorAll('[data-original-label]').forEach(button=>{button.textContent=button.dataset.originalLabel;button.disabled=false;button.removeAttribute('aria-busy');}));
})();
