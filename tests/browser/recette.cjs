/* Isolated Edge -> native executable -> fictitious encrypted Qt vault. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn,spawnSync}=require('node:child_process'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../..');
const python=process.env.VAULTSAFE_TEST_PYTHON||path.join(root,'.venv/Scripts/python.exe');
const executable=process.env.VAULTSAFE_TEST_EXE||path.join(root,'dist/VaultSafe/VaultSafe.exe');
const edge=process.env.VAULTSAFE_TEST_BROWSER||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const version=JSON.parse(fs.readFileSync(path.join(root,'extension/manifest.json'),'utf8')).version;
const id='egbpodcdijmeibnmfabhiignfppmclbl',host='org.vaultsafe.recette';
const key='HKCU\\Software\\Microsoft\\Edge\\NativeMessagingHosts\\'+host;
const fake='Fictif-navigateur-2026!',dir=fs.mkdtempSync(path.join(os.tmpdir(),'vaultsafe-browser-'));
fs.writeFileSync(path.join(dir,'fixture-owned.json'),JSON.stringify({fictif:true}));
const data=path.join(dir,'donnees'),pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(f,ms=15000){const end=Date.now()+ms;while(Date.now()<end){try{const v=await f();if(v)return v;}catch{}await pause(80);}throw Error('Timed out: '+f.toString().slice(0,120));}
const read=()=>JSON.parse(fs.readFileSync(path.join(dir,'etat.json'),'utf8'));
let sequence=0,fixture,context,registered=false,checks=0,sitePage;
async function cmd(action,extra={}){const n=++sequence;fs.writeFileSync(path.join(dir,'commande.json'),JSON.stringify({sequence:n,action,...extra}));return until(()=>{const s=read();return s.sequence===n?s:null;});}
const state=()=>cmd('view'),ok=name=>{checks++;process.stdout.write('OK '+name+'\n');};
const html=kind=>`<!doctype html><html><body><form method="post" action="/done"><input name="username" autocomplete="username"><input name="password" type="password" autocomplete="${kind==='inscription'?'new-password':'current-password'}"><button>${kind==='inscription'?'Créer un compte':'Connexion'}</button></form></body></html>`;
const panel=page=>until(async()=>{
 for(const f of page.frames())if(f.url().startsWith(`chrome-extension://${id}/capture-panel.html`)){
  try{if(await f.locator('#formulaire').isVisible()||await f.locator('#ouvrir').isVisible())return f;}catch{}
 }
 return null;
});
async function submit(page,url,user,mot=fake){await page.goto(url);await page.locator('[name=username]').fill(user);await page.locator('[type=password]').fill(mot);await page.locator('form button').click();}
async function save(page,label='Enregistrer'){const f=await panel(page);await f.locator('#sauver').filter({hasText:label}).click();await f.locator('#message').filter({hasText:/enregistré|mis à jour/}).waitFor();}
(async()=>{try{
 assert.equal(spawnSync('reg.exe',['query',key],{windowsHide:true}).status,1,'Refuse to replace an existing fixture host');
 const ext=path.join(dir,'extension');fs.cpSync(path.join(root,'extension'),ext,{recursive:true});
 const bg=path.join(ext,'background.js');fs.writeFileSync(bg,fs.readFileSync(bg,'utf8').replace('org.vaultsafe.local',host));
 fixture=spawn(python,['-B',path.join(__dirname,'fixture_qt.py'),'--repertoire',dir,'--executable',executable],{windowsHide:true,env:{...process.env,VAULTSAFE_DATA_DIR:data,QT_QPA_PLATFORM:'offscreen',PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','ignore','pipe']});
 let err='';fixture.stderr.on('data',b=>err+=b.toString());
 await until(()=>fs.existsSync(path.join(dir,'etat.json'))).catch(e=>{throw Error(e.message+' '+err.slice(-1800));});
 const manifest=path.join(dir,'host.json');fs.writeFileSync(manifest,JSON.stringify({name:host,description:'Fictitious qualification',path:executable,type:'stdio',allowed_origins:[`chrome-extension://${id}/`]}));
 assert.equal(spawnSync('reg.exe',['add',key,'/ve','/t','REG_SZ','/d',manifest,'/f'],{windowsHide:true}).status,0);registered=true;
 context=await chromium.launchPersistentContext(path.join(dir,'profile'),{executablePath:edge,headless:true,args:[`--disable-extensions-except=${ext}`,`--load-extension=${ext}`],env:{...process.env,VAULTSAFE_DATA_DIR:data}});
 await context.route('https://recette.example/**',async route=>{
  const u=new URL(route.request().url());if(u.pathname==='/done')return route.fulfill({contentType:'text/html',body:'<!doctype html><h1>Bienvenue</h1>'});
  let body=html('connexion');
  if(u.pathname==='/spa')body=body.replace('</form>','</form><script>document.querySelector("form").onsubmit=e=>{e.preventDefault();document.querySelector("form").innerHTML="Bienvenue";history.pushState({},"","/spa-done")}</script>');
  if(u.pathname==='/refus')body=body.replace('</form>','</form><script>document.querySelector("form").onsubmit=e=>{e.preventDefault();const p=document.createElement("p");p.setAttribute("role","alert");p.textContent="Mot de passe incorrect";document.body.append(p)}</script>');
  if(u.pathname==='/inscription')body=html('inscription');
  if(u.pathname==='/change-password')body='<!doctype html><form method="post" action="/done"><input name="username" autocomplete="username"><label>Mot de passe actuel<input type="password" name="p1"></label><label>Nouveau mot de passe<input type="password" name="p2"></label><label>Confirmation<input type="password" name="p3"></label><button>Enregistrer</button></form>';
  if(u.pathname==='/modal')body=body.replace('<form','<dialog open><form').replace('</form>','</form></dialog><script>document.querySelector("dialog").close();document.querySelector("dialog").showModal()</script>');
  if(u.pathname==='/deux')body='<!doctype html><form><input autocomplete="username" name="username"><button>Continuer</button></form><script>document.querySelector("form").onsubmit=e=>{e.preventDefault();document.querySelector("form").innerHTML=\'<input type="password" name="password" autocomplete="current-password"><button>Connexion</button>\';document.querySelector("form").onsubmit=e=>{e.preventDefault();location.href="/done"}}</script>';
  if(u.pathname==='/classic')body=body.replace('<html>','<html style="zoom:1.25">').replace('<body>','<body style="transform:translate(25px,20px)">');
  return route.fulfill({contentType:'text/html',body});
 });
 const page=sitePage=await context.newPage();
 await submit(page,'https://recette.example/classic','classique@example.test');await save(page);assert.equal((await state()).nombre,1);assert.equal((await state()).confirmations_windows,0);ok('classic/redirection/zoom one-click save');
 await submit(page,'https://recette.example/classic','classique@example.test');await pause(1800);assert.equal((await state()).nombre,1);ok('duplicate');
 await submit(page,'https://recette.example/spa','spa@example.test');await save(page);assert.equal((await state()).nombre,2);ok('dynamic clearing');
 await submit(page,'https://recette.example/inscription','inscription@example.test');await save(page);assert.equal((await state()).nombre,3);ok('registration');
 await submit(page,'https://recette.example/modal','modal@example.test');await save(page);assert.equal((await state()).nombre,4);ok('modal');
 await page.goto('https://recette.example/deux');await page.locator('[name=username]').fill('etapes@example.test');await page.locator('button').click();await page.locator('[type=password]').fill(fake);await page.locator('button').click();await save(page);assert.equal((await state()).nombre,5);ok('two-step login');
 await cmd('mode',{mode:'automatique'});await submit(page,'https://recette.example/classic','automatique@example.test');await until(async()=>(await state()).nombre===6);ok('automatic new account');
 await submit(page,'https://recette.example/refus','classique@example.test','Tentative-fictive-refusee!');const refused=await panel(page);await refused.locator('#message').filter({hasText:/refusée/}).waitFor();assert.equal((await state()).historique,0);await refused.locator('#ignorer').click();await until(()=>!page.frames().some(f=>f.url().startsWith(`chrome-extension://${id}/capture-panel.html`)));ok('refused update preserves valid account');
 await cmd('mode',{mode:'proposition'});await submit(page,'https://recette.example/classic','classique@example.test','Nouveau-fictif!');await save(page,'Mettre à jour');assert.equal((await state()).nombre,6);assert.equal((await state()).historique,1);ok('update and history');
 await page.goto('https://recette.example/change-password');await page.locator('[name=username]').fill('classique@example.test');await page.locator('[name=p1]').fill('Nouveau-fictif!');await page.locator('[name=p2]').fill('Changement-fictif-2026!');await page.locator('[name=p3]').fill('Changement-fictif-2026!');await page.locator('button').click();await save(page,'Mettre à jour');assert.equal((await state()).nombre,6);assert.equal((await state()).historique,2);ok('password-change form without autocomplete preserves account/history');
 await cmd('lock');await submit(page,'https://recette.example/classic','verrou@example.test');const locked=await panel(page);await locked.locator('#ouvrir').waitFor();assert.equal(await locked.locator('#formulaire').isVisible(),false);ok('locked without false saved result');
 await cmd('unlock');await page.goto('https://recette.example/classic');
 const worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');
 const storage=await worker.evaluate(async()=>JSON.stringify({local:await chrome.storage.local.get(null),session:await chrome.storage.session.get(null)}));assert(!storage.includes(fake)&&!storage.includes('Nouveau-fictif!'));ok('no plaintext password in extension storage');
 const active=await worker.evaluate(async()=>(await chrome.tabs.query({active:true})).find(t=>t.url?.startsWith('https://recette.example')));assert(active);
 const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await popup.evaluate(t=>{chrome.tabs.query=async()=>[t]},active);await page.bringToFront();await popup.locator('#actualiser').click();await popup.locator('[data-page=generateur]').click();
 await popup.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{value:{writeText:async v=>{globalThis.fakeClipboard=v}},configurable:true})});await popup.locator('#copier').click();assert.equal(await popup.evaluate(()=>globalThis.fakeClipboard===document.querySelector('#genere').value),true);await popup.evaluate(()=>globalThis.fakeClipboard='');ok('copy icon with in-memory clipboard');
 await popup.locator('#utiliser').click();assert.equal(await page.locator('[type=password]').inputValue(),await popup.locator('#genere').inputValue());ok('generator insertion');
 await popup.locator('[data-page=remplissage]').click();await popup.locator('#actualiser').click();await popup.locator('#fiches button').first().click();await until(async()=>(await state()).confirmations_windows===1);ok('native exact-origin fill');
 const before=(await state()).nombre;assert.equal((await cmd('reopen')).nombre,before);assert(!fs.readFileSync(path.join(data,'fictif.db')).includes(Buffer.from(fake)));ok('encrypted persistence');
 const rapport={checks,browser:'isolated Edge',extension:version,nativeExecutable:true,fakeVault:true};
 if(process.argv[2])fs.writeFileSync(path.resolve(process.argv[2]),JSON.stringify(rapport,null,2));
 process.stdout.write(JSON.stringify(rapport)+'\n');
 }catch(e){
  if(sitePage){
   const diagnostics={checks,state:await state().catch(()=>null),page:await sitePage.evaluate(()=>({path:location.pathname,host:!!document.querySelector('vaultsafe-proposition')})).catch(()=>null),frames:[]};
   for(const f of sitePage.frames())if(f.url().includes('/capture-panel.html'))diagnostics.frames.push(await f.evaluate(()=>({message:document.querySelector('#message')?.textContent,formVisible:!document.querySelector('#formulaire')?.hidden,ouvrirVisible:!document.querySelector('#ouvrir')?.hidden})).catch(()=>({detached:true})));
   process.stderr.write(JSON.stringify(diagnostics)+'\n');
  }
  throw e;
 }finally{
  if(context)await context.close();
  if(fixture&&fixture.exitCode===null){fs.writeFileSync(path.join(dir,'commande.json'),JSON.stringify({sequence:++sequence,action:'stop'}));await pause(800);if(fixture.exitCode===null)fixture.kill();}
  if(registered)spawnSync('reg.exe',['delete',key,'/f'],{windowsHide:true});
  assert(dir.startsWith(path.join(os.tmpdir(),'vaultsafe-browser-')));fs.rmSync(dir,{recursive:true,force:true,maxRetries:8,retryDelay:250});
 }
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
