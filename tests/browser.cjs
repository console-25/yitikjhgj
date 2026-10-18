// Usage: BASE_URL=http://127.0.0.1:8082 CREDENTIALS=/private/credentials.json node tests/browser.cjs
// The app must run in a disposable database with explicit development demo accounts.
const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-gpu','--no-zygote']});
 const credentials=JSON.parse(fs.readFileSync(process.env.CREDENTIALS,'utf8'));
 const failures=[];let checks=0;
 for(const width of [1920,1440,1024,768,390,360]){
  const context=await browser.newContext({viewport:{width,height:900}});
  const page=await context.newPage();page.on('pageerror',e=>failures.push('pageerror: '+String(e)));
  await page.setExtraHTTPHeaders({'X-Forwarded-For':'198.51.100.'+width});
  page.on('console',message=>{if(message.type()==='error'&&!message.text().includes('net::ERR_FAILED'))failures.push('console: '+message.text());});
  await page.route('**/*',route=>new URL(route.request().url()).origin===new URL(process.env.BASE_URL).origin?route.continue():route.abort());
  for(const email of ['client@noryx.test','admin@noryx.test']){
   await page.goto(process.env.BASE_URL+'/login');
   if(await page.locator('input[name=email]').inputValue())throw Error('Login autofilled');
   const formWidth=await page.locator('.auth-card').evaluate(e=>e.getBoundingClientRect().width);
   if(formWidth<280||formWidth>width+1)failures.push('Auth card width invalid at '+width+': '+formWidth);
   if(width<721){
    if(await page.locator('.auth-intro').isVisible())failures.push('Desktop auth intro visible on mobile '+width);
    await page.getByRole('button',{name:'Open navigation'}).count();
   }
   await page.locator('input[name=email]').fill(email);await page.locator('input[name=password]').fill(credentials[email]);
   await page.getByRole('button',{name:/Sign in/}).click();await page.waitForURL('**/dashboard');
   const expected=email.startsWith('admin')?'/admin/dashboard':'/client/dashboard';
   if(!page.url().endsWith(expected))throw Error('Role redirect mismatch');
   const routes=email.startsWith('admin')?['/admin/dashboard','/admin/users','/admin/users/1','/admin/users/1?tab=profile','/admin/users/1?tab=security','/admin/users/new','/admin/catalog','/admin/plans/new','/admin/orders','/admin/tickets','/admin/content','/admin/audit']:['/client/dashboard','/catalog','/checkout/1','/client/services','/client/orders','/client/invoices','/client/wallet','/client/tickets','/client/account'];
   for(const path of routes){
    const response=await page.goto(process.env.BASE_URL+path);
    if(response.status()!==200)failures.push(path+': '+response.status()+' at '+width);
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))failures.push(path+': horizontal overflow at '+width);
    if(!(await page.locator('h1').innerText()).trim())failures.push(path+': missing heading');checks++;
   }
   if(email.startsWith('admin')&&width===1440){
    await page.goto(process.env.BASE_URL+'/admin/plans/new');
    for(let step=0;step<3;step++)await page.getByRole('button',{name:'Continue →'}).click();
    if(!await page.getByRole('tab',{name:'Plan details'}).getAttribute('aria-selected')||await page.getByRole('tab',{name:'Plan details'}).getAttribute('aria-selected')!=='true')throw Error('Guided plan editor did not reach final step');
    await page.locator('input[name=name]').fill('Browser verified plan');
    await page.getByRole('tab',{name:'Pricing'}).click();await page.locator('input[name=amount]').fill('9750');await page.locator('input[name=setup_fee]').fill('0');
    await page.getByRole('tab',{name:'Availability'}).click();await page.locator('input[name=stock]').fill('3');await page.locator('select[name=status]').selectOption('published');
    await page.getByRole('button',{name:'Save plan changes'}).click();await page.waitForURL('**/admin/catalog');
    await page.goto(process.env.BASE_URL+'/catalog');if(!(await page.locator('body').innerText()).includes('Browser verified plan'))throw Error('Saved plan missing from public catalog');checks++;
    await page.goto(process.env.BASE_URL+'/admin/users/1?tab=profile');
    await page.locator('input[name=first_name]').fill('Console');await page.locator('input[name=last_name]').fill('Client');
    await page.locator('form').filter({has:page.locator('input[name="action"][value="profile"]')}).locator('input[name=current_password]').fill(credentials[email]);
    await page.getByRole('button',{name:'Save profile'}).click();await page.waitForURL('**/admin/users/1?tab=profile');
    if(!(await page.locator('.profile-title h1').innerText()).includes('Console Client'))throw Error('Edited profile did not appear after save');
    const clientContext=await browser.newContext({viewport:{width,height:900}});const clientPage=await clientContext.newPage();await clientPage.setExtraHTTPHeaders({'X-Forwarded-For':'198.51.100.'+width});
    await clientPage.goto(process.env.BASE_URL+'/login');await clientPage.locator('input[name=email]').fill('client@noryx.test');await clientPage.locator('input[name=password]').fill(credentials['client@noryx.test']);await clientPage.getByRole('button',{name:/Sign in/}).click();await clientPage.waitForURL('**/dashboard');
    if(!(await clientPage.locator('body').innerText()).includes('Welcome back, Console'))throw Error('Updated customer profile was not reflected in client panel');
    await clientContext.close();
   }
   if(email.startsWith('client')){
    await page.goto(process.env.BASE_URL+'/client/tickets');await page.getByText('Open a support ticket',{exact:true}).click();
    await page.locator('input[name=subject]').fill('Browser support test');await page.locator('textarea[name=body]').fill('Please review my hosting request.');
    await page.getByRole('button',{name:'Create ticket'}).click();await page.waitForURL('**/tickets/*');
    if(!await page.getByText('Please review my hosting request.').isVisible())throw Error('Ticket not persisted');
   }
   if(width<721&&email.startsWith('client')){
    await page.getByRole('button',{name:'Open navigation'}).click();
    if(!(await page.locator('body').evaluate(e=>e.classList.contains('menu-open'))))throw Error('Mobile drawer did not open');
    await page.keyboard.press('Escape');
    if(await page.locator('body').evaluate(e=>e.classList.contains('menu-open')))throw Error('Escape did not close mobile drawer');
   }
   await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/login');
  }
  for(const path of ['/about/','/careers/','/']){
   const response=await page.goto(process.env.BASE_URL+path);await page.waitForTimeout(200);
   if(response.status()!==200)failures.push(path+': HTTP '+response.status());
   if(path==='/about/'&&!((await page.locator('body').innerText()).includes('Console')))failures.push('About team missing');checks++;
  }
  if(process.env.SCREENSHOT_DIR){await page.goto(process.env.BASE_URL+'/login');await page.waitForTimeout(500);await page.screenshot({path:process.env.SCREENSHOT_DIR+'/login-'+width+'.png',fullPage:true});}
  await context.close();
 }
 await browser.close();console.log(JSON.stringify({checks,failures},null,2));if(failures.length)process.exit(1);
})().catch(error=>{console.error(error);process.exit(1)});
