'use strict';
(() => {
  const body = document.body;
  const menu = document.querySelector('[data-menu-toggle]');
  const sidebar = document.querySelector('#app-sidebar');
  const mobile = window.matchMedia('(max-width: 720px)');
  const syncDrawer = () => { if (sidebar) sidebar.inert = mobile.matches && !body.classList.contains('menu-open'); };
  const closeMenu = () => { const wasOpen=body.classList.contains('menu-open'); body.classList.remove('menu-open'); menu?.setAttribute('aria-expanded','false'); syncDrawer(); if(wasOpen)menu?.focus(); };
  menu?.addEventListener('click', () => {
    const opened = body.classList.toggle('menu-open');
    menu.setAttribute('aria-expanded', String(opened)); syncDrawer();
    if(opened)sidebar?.querySelector('a')?.focus();
  });
  document.querySelector('[data-menu-close]')?.addEventListener('click',closeMenu);
  mobile.addEventListener('change',()=>{body.classList.remove('menu-open');menu?.setAttribute('aria-expanded','false');syncDrawer();});
  syncDrawer();
  document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu();});
  document.querySelector('[data-collapse-toggle]')?.addEventListener('click',()=>{
    const compact=body.classList.toggle('sidebar-compact');
    localStorage.setItem('noryx-sidebar-compact',compact?'1':'0');
  });
  if(localStorage.getItem('noryx-sidebar-compact')==='1')body.classList.add('sidebar-compact');
  document.querySelectorAll('nav a').forEach(link=>{
    const match=link.pathname===location.pathname||(link.pathname!=='/'&&location.pathname.startsWith(link.pathname+'/'));
    if(match){link.setAttribute('aria-current','page');link.closest('details')?.setAttribute('open','');}
    if(link.closest('.sidebar'))link.title=link.textContent.trim();
  });
  document.querySelectorAll('[data-toggle-password]').forEach(button=>button.addEventListener('click',()=>{
    const input=document.getElementById(button.getAttribute('aria-controls'));
    const show=input.type==='password'; input.type=show?'text':'password';
    button.textContent=show?'Hide':'Show'; button.setAttribute('aria-label',show?'Hide password':'Show password');
  }));
  document.querySelectorAll('form').forEach(form=>form.addEventListener('submit',event=>{
    const submitter=event.submitter;
    if(submitter?.dataset.confirm&&!window.confirm(submitter.dataset.confirm)){event.preventDefault();return;}
    if(form.dataset.confirm&&!window.confirm(form.dataset.confirm)){event.preventDefault();return;}
    if(!form.matches('[data-plan-wizard]')&&!form.checkValidity()){event.preventDefault();form.reportValidity();return;}
    if(!form.matches('[data-plan-wizard]')&&submitter&&form.method.toLowerCase()==='post'&&!submitter.dataset.keepLabel){
      submitter.dataset.originalLabel=submitter.textContent.trim();
      submitter.innerHTML='<span class="loading-spinner" aria-hidden="true"></span><span>Working…</span>';
      submitter.disabled=true;submitter.setAttribute('aria-busy','true');
    }
  }));
  document.querySelectorAll('.toast-close').forEach(button=>button.addEventListener('click',()=>{
    const toast=button.closest('.toast'); if(!toast)return;
    const animation=toast.animate([{opacity:1,transform:'translateY(0)'},{opacity:0,transform:'translateY(-5px)'}],{duration:160,easing:'ease-in'});
    animation.onfinish=()=>toast.remove();
  }));
  document.querySelector('[data-select-all]')?.addEventListener('change',event=>{
    const form=event.target.closest('form');
    form?.querySelectorAll('input[name="user_ids"]').forEach(input=>input.checked=event.target.checked);
  });
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reveals=[...document.querySelectorAll('.card:not(.auth-card), .stat-card, .record-row')];
  if('IntersectionObserver' in window&&!reduce){
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(entry.isIntersecting){entry.target.classList.add('is-visible');observer.unobserve(entry.target);}
    }),{threshold:.08});
    reveals.forEach((element,index)=>{element.dataset.enter='';element.style.transitionDelay=Math.min(index%5,4)*35+'ms';observer.observe(element);});
  }
  document.querySelectorAll('[data-count]').forEach(element=>{
    const target=Number(element.dataset.count);
    if(reduce||!Number.isFinite(target)||target>99999||target===0)return;
    const suffix=element.textContent.replace(/[\d,\s]/g,'');
    const format=n=>Math.round(n).toLocaleString('en-US')+suffix;
    let start;
    const run=time=>{if(!start)start=time;const progress=Math.min((time-start)/520,1);const eased=1-Math.pow(1-progress,3);element.textContent=format(target*eased);if(progress<1)requestAnimationFrame(run);};
    const observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){requestAnimationFrame(run);observer.disconnect();}},{threshold:.7});observer.observe(element);
  });
})();
  document.querySelectorAll('[data-plan-wizard]').forEach(form=>{
    const steps=['category','location','processor','plan'];
    const tabs=[...form.querySelectorAll('[data-step-tab]')];
    const panes=[...form.querySelectorAll('[data-step-pane]')];
    let current=Math.max(0,steps.indexOf(form.dataset.initialStep));
    const save=form.querySelector('.wizard-save');
    const next=form.querySelector('[data-step-next]');
    const prev=form.querySelector('[data-step-prev]');
    const progress=form.querySelector('.step-progress span');
    const setStep=index=>{
      current=Math.max(0,Math.min(index,steps.length-1));
      panes.forEach(pane=>pane.hidden=pane.dataset.stepPane!==steps[current]);
      tabs.forEach((tab,i)=>{
        tab.classList.toggle('active',i===current);
        tab.classList.toggle('complete',i<current);
        tab.setAttribute('aria-selected',String(i===current));
        tab.disabled=i>current;
      });
      if(progress)progress.style.width=`${current/(steps.length-1)*100}%`;
      if(prev)prev.hidden=current===0;
      if(next)next.hidden=current===steps.length-1;
      if(save)save.hidden=current!==steps.length-1;
    };
    const validateStep=()=>{
      const pane=panes.find(item=>item.dataset.stepPane===steps[current]);
      const field=[...pane.querySelectorAll('input,select,textarea')].find(item=>!item.checkValidity());
      if(field){field.reportValidity();return false;}
      return true;
    };
    next?.addEventListener('click',()=>{if(validateStep())setStep(current+1);});
    prev?.addEventListener('click',()=>setStep(current-1));
    tabs.forEach((tab,index)=>tab.addEventListener('click',()=>{
      if(index<=current&&validateStep())setStep(index);
    }));
    form.querySelector('[name="category_id"]')?.addEventListener('change',event=>{
      const label=event.target.selectedOptions[0]?.textContent.trim();
      const preview=form.querySelector('[data-category-preview]');if(preview)preview.textContent=label||'Choose a category';
    });
    const editorTabs=[...form.querySelectorAll('[data-editor-tab]')];
    const activateEditorTab=tab=>{
      editorTabs.forEach(item=>{item.classList.toggle('active',item===tab);item.setAttribute('aria-selected',String(item===tab));});
      form.querySelectorAll('[data-editor-pane]').forEach(pane=>pane.hidden=pane.dataset.editorPane!==tab.dataset.editorTab);
    };
    editorTabs.forEach((tab,index)=>{
      tab.addEventListener('click',()=>activateEditorTab(tab));
      tab.addEventListener('keydown',event=>{
        let target=null;
        if(event.key==='ArrowRight')target=editorTabs[(index+1)%editorTabs.length];
        if(event.key==='ArrowLeft')target=editorTabs[(index-1+editorTabs.length)%editorTabs.length];
        if(event.key==='Home')target=editorTabs[0];
        if(event.key==='End')target=editorTabs.at(-1);
        if(target){event.preventDefault();target.focus();activateEditorTab(target);}
      });
    });
    form.addEventListener('submit',event=>{
      const invalid=[...form.querySelectorAll('input[required],select[required],textarea[required]')].find(field=>!field.checkValidity());
      if(invalid){
        const editor=invalid.closest('[data-editor-pane]');
        if(editor)form.querySelector(`[data-editor-tab="${editor.dataset.editorPane}"]`)?.click();
        setStep(steps.length-1);event.preventDefault();invalid.reportValidity();return;
      }
      if(save){save.innerHTML='<span class="loading-spinner" aria-hidden="true"></span><span>Saving…</span>';save.disabled=true;save.setAttribute('aria-busy','true');}
    });
    setStep(current);
  });
