// Monde isolé. Secrets lus uniquement au geste de connexion, jamais par polling.
(() => {
  if (top !== window || (location.protocol !== 'https:' && !(location.protocol === 'http:' &&
      ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)))) return;
  window.__vaultsafeCapture?.arreter?.();
  const ecoute = new AbortController(), options = { capture:true, passive:true, signal:ecoute.signal };
  const origine = location.origin, version = chrome.runtime.getManifest().version;
  let politique = {mode:'proposition',exclus:[]}, dernierUtilisateur='', utilisateurExpire=0,
    dernierEnvoi=0, interaction=0, panneau, enveloppe, resultatObserve, resultatTimer,
    placementObserve, placementFrame, hauteurPanneau=310;
  const visible = e => !e.disabled && !e.closest('[hidden],[inert],[aria-hidden="true"]') &&
    e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' &&
    getComputedStyle(e).display !== 'none' && Number(getComputedStyle(e).opacity)>0;
  const actif = () => politique.mode !== 'desactive' && !politique.exclus.includes(origine);
  const motToken = (e, token) => e.autocomplete.toLowerCase().split(/\s+/).includes(token);
  function fermerPanneau() {
    placementObserve?.disconnect();cancelAnimationFrame(placementFrame);
    enveloppe?.remove();panneau=null;enveloppe=null;
  }
  function placerPanneau() {
    if(!enveloppe)return;
    // Un dialogue modal rend les éléments extérieurs inertes, même dans la couche supérieure.
    const modaux=[...document.querySelectorAll('dialog:modal')];
    const parent=modaux.at(-1)||document.documentElement;
    if(enveloppe.parentElement!==parent)parent.append(enveloppe);
    let zoom=1;
    for(let p=parent;p instanceof Element;p=p.parentElement)zoom*=parseFloat(getComputedStyle(p).zoom)||1;
    const fixer=(cle,valeur)=>{if(enveloppe.style.getPropertyValue(cle)!==valeur)enveloppe.style.setProperty(cle,valeur,'important');};
    fixer('zoom',String(1/zoom));
    fixer('height',Math.max(1,Math.min(hauteurPanneau,innerHeight-32))+'px');
    if(typeof enveloppe.showPopover==='function'&&!enveloppe.matches(':popover-open'))enveloppe.showPopover();
  }
  function arreter() {
    ecoute.abort(); resultatObserve?.disconnect(); clearTimeout(resultatTimer);
    dernierUtilisateur=''; utilisateurExpire=0; fermerPanneau();
    try { chrome.runtime.onMessage.removeListener(repondre); } catch { /* Contexte expiré. */ }
  }
  function envoyer(message) {
    try { return chrome.runtime.sendMessage(message).finally(()=>{message.mot_de_passe='';message.utilisateur='';}); }
    catch { message.mot_de_passe=''; message.utilisateur=''; arreter(); return Promise.reject(Error('Contexte expiré.')); }
  }
  function repondre(message, sender, reponse) {
    if(sender.id !== chrome.runtime.id) return false;
    if(message?.action==='capture_status') reponse({ok:true,origine,version});
    if(message?.action==='capture_policy_update') {
      politique=message.options; if(!actif()) { dernierUtilisateur=''; fermerPanneau(); }
      reponse({ok:true});
    }
    if(message?.action==='capture_panel' && /^[A-Za-z0-9_-]{16,64}$/.test(message.id)) {
      // Plusieurs réponses peuvent rejoindre la fin d'une navigation : conserver le cadre en cours.
      if(enveloppe?.isConnected && panneau?.src.endsWith('#'+message.id)) { placerPanneau();reponse({ok:true});return false; }
      fermerPanneau();hauteurPanneau=310;
      enveloppe=document.createElement('vaultsafe-proposition');
      enveloppe.style.cssText='all:initial!important;position:fixed!important;inset:auto!important;right:16px!important;top:16px!important;width:min(320px,calc(100vw - 32px))!important;height:min(310px,calc(100vh - 32px))!important;box-sizing:border-box!important;margin:0!important;padding:0!important;border:0!important;border-radius:16px!important;z-index:2147483647!important;background:transparent!important;box-shadow:0 8px 28px #0002!important;color-scheme:normal!important;display:block!important;visibility:visible!important;opacity:1!important;pointer-events:auto!important;';
      if(typeof enveloppe.showPopover==='function')enveloppe.setAttribute('popover','manual');
      const racine=enveloppe.attachShadow({mode:'closed'});
      panneau=document.createElement('iframe');
      panneau.src=chrome.runtime.getURL('capture-panel.html')+'#'+message.id;
      panneau.title='Enregistrement VaultSafe';
      panneau.style.cssText='width:100%;height:100%;display:block;border:0;border-radius:16px;background:transparent;';
      racine.append(panneau);placerPanneau();
      placementObserve=new MutationObserver(()=>{
        cancelAnimationFrame(placementFrame);placementFrame=requestAnimationFrame(placerPanneau);
      });
      placementObserve.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['open','style','class']});
      reponse({ok:true});
    }
    if(message?.action==='capture_close') {
      if(panneau?.src.endsWith('#'+message.id))fermerPanneau();reponse({ok:true});
    }
    if(message?.action==='capture_resize' && panneau && panneau.src.endsWith('#'+message.id)) {
      hauteurPanneau=Math.max(100,message.hauteur);placerPanneau();reponse({ok:true});
    }
    if(message?.action==='capture_panel_valid') {
      placerPanneau();
      const r=panneau?.getBoundingClientRect(),s=enveloppe&&getComputedStyle(enveloppe);
      const bonnes=Boolean(r&&panneau.src.endsWith('#'+message.id)&&s.display!=='none'&&s.visibility==='visible'&&
        Number(s.opacity)>.98&&r.width>=220&&r.height>=100&&r.top>=0&&r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&
        document.elementFromPoint(r.left+r.width/2,r.top+35)===enveloppe);
      reponse({ok:bonnes});
    }
    return false;
  }
  chrome.runtime.onMessage.addListener(repondre);
  window.addEventListener('resize',placerPanneau,options);
  window.__vaultsafeCapture={arreter};
  envoyer({action:'capture_policy',origine}).then(r=>{if(r?.options)politique=r.options;}).catch(()=>{});
  window.addEventListener('focus',()=>envoyer({action:'capture_policy',origine}).then(r=>{
    if(r?.options)politique=r.options;
  }).catch(()=>{}),options);
  const utilisateur = zone => {
    const tous=[...zone.querySelectorAll('input:not([type]),input[type="text"],input[type="email"],input[type="tel"]')]
      .filter(e=>visible(e)&&!motToken(e,'one-time-code')&&!/password/i.test(e.autocomplete));
    const explicites=tous.filter(e=>motToken(e,'username')||motToken(e,'email')||e.type==='email'||
      /user|login|email|mail|identifiant/i.test(e.name+' '+e.id));
    return (explicites.length===1?explicites[0]:tous.length===1?tous[0]:null)?.value.trim().slice(0,200)||'';
  };
  function resultat() {
    const erreurs=[...document.querySelectorAll('[role="alert"],[aria-invalid="true"],.error-message,.error,.text-error-primary')].filter(visible);
    return erreurs.some(e=> e.getAttribute('aria-invalid')==='true' ||
      /incorrect|invalid|wrong|failed|échou|refus|not match|not registered|not found|mauvais|invalide/i.test(e.textContent)) ? 'echec':'incertain';
  }
  function surveiller(soumission, envoi) {
    resultatObserve?.disconnect(); clearTimeout(resultatTimer);
    let dernier='incertain';
    const verifier=()=>{
      const etat=resultat();
      if(etat!==dernier) {
        dernier=etat;
        // Le refus peut apparaître avant que capture_begin ait fini de lire le coffre.
        envoi.then(r=>{if(r?.ok&&!r.ignore)envoyer({action:'capture_result',origine,soumission,resultat:etat}).catch(()=>{});}).catch(()=>{});
      }
    };
    resultatObserve=new MutationObserver(verifier);
    resultatObserve.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['aria-invalid','class','hidden']});
    resultatTimer=setTimeout(()=>{verifier();resultatObserve?.disconnect();},6000);
  }
  function saisir(zone, intention='') {
    if(!actif()||location.origin!==origine||document.visibilityState!=='visible')return;
    if(zone instanceof HTMLFormElement && ((!zone.noValidate&&!zone.checkValidity())||
        new URL(zone.action||location.href,location.href).origin!==origine))return;
    const mots=[...zone.querySelectorAll('input[type="password"],input[autocomplete~="current-password"],input[autocomplete~="new-password"]')]
      .filter(visible).filter(e=>!motToken(e,'one-time-code')&&!/(?:^|[-_])(otp|totp|2fa|verificationcode)(?:$|[-_])/i.test(e.name+' '+e.id));
    const nom=utilisateur(zone);
    if(!mots.length) {
      if(nom && /login|signin|log in|sign in|connect|connexion|continuer|continue|next|suivant|créer|create|register/i.test(intention+' '+(zone.id||'')) &&
          !/newsletter|subscribe|abonner|search|rechercher/i.test(intention)) {
        dernierUtilisateur=nom;utilisateurExpire=Date.now()+120000;
        envoyer({action:'login_step',origine,utilisateur:nom}).catch(()=>{});
      }
      return;
    }
    if(mots.length>3||mots.some(e=>e.form&&new URL(e.form.action||location.href,location.href).origin!==origine))return;
    let mot=mots[0],type='connexion';
    const description=e=>[e.name,e.id,e.placeholder,e.getAttribute('aria-label'),...[...(e.labels||[])].map(l=>l.textContent)].join(' ');
    const changement=/change|reset|modifier|changer|mise.*jour|update.*password/i.test(intention+' '+location.pathname);
    const nouveaux=mots.filter(e=>motToken(e,'new-password')||/new|nouveau|confirm|repeat|répét/i.test(description(e)));
    const anciens=mots.filter(e=>motToken(e,'current-password')||/old|current|ancien|actuel/i.test(description(e)));
    if(mots.length>1) {
      if(nouveaux.length && anciens.length===1 && !nouveaux.includes(anciens[0])) {
        if(nouveaux.length>2||nouveaux.some(e=>e.value!==nouveaux[0].value))return;
        mot=nouveaux[0];type='changement';
      } else if(changement && mots.length===3 && mots.every(e=>e.form&&e.form===mots[0].form) &&
          mots[1].value && mots[1].value===mots[2].value && mots[0].value!==mots[1].value) {
        mot=mots[1];type='changement';
      } else if(mots.length===2 && mots[0].value===mots[1].value && mots[0].form && mots[0].form===mots[1].form) {
        mot=mots[0];type='inscription';
      } else return;
    } else if(motToken(mot,'new-password')||/sign.?up|inscri|register|créer|create account/i.test(intention))type='inscription';
    if(changement)type='changement';
    if(!mot.value||mot.value.length>4096||Date.now()-dernierEnvoi<1500)return;
    dernierEnvoi=Date.now();const soumission=crypto.randomUUID();
    const envoi=envoyer({action:'capture',origine,soumission,url:origine+location.pathname,type,utilisateur:nom||
      (Date.now()<utilisateurExpire?dernierUtilisateur:''),mot_de_passe:mot.value});
    surveiller(soumission,envoi);envoi.catch(()=>{});
    dernierUtilisateur='';utilisateurExpire=0;
  }
  document.addEventListener('input',e=>{
    if(actif()&&e.isTrusted&&e.target instanceof HTMLInputElement&&
        (e.target.type==='email'||motToken(e.target,'username'))) {
      dernierUtilisateur=e.target.value.trim().slice(0,200);utilisateurExpire=Date.now()+120000;
    }
  },options);
  document.addEventListener('click',e=>{
    if(!e.isTrusted||!(e.target instanceof Element))return;
    interaction=Date.now();const b=e.target.closest('button,input[type="submit"],input[type="image"],[role="button"]');
    if(!b||b.disabled)return;
    const intention=b.innerText+' '+(b.value||'')+' '+(b.getAttribute('aria-label')||'');
    if(!/log[ -]?in|sign[ -]?in|connecter|connexion|continue|continuer|next|suivant|sign[ -]?up|inscri|create account|créer|register|change.*password|changer.*passe|modifier.*passe|save.*password|update.*password|enregistrer.*passe|reset/i.test(intention)&&
        !(b.form&&b.type==='submit'))return;
    saisir(b.form||b.closest('form,[role="form"]')||document,intention);
  },options);
  document.addEventListener('keydown',e=>{
    if(!e.isTrusted)return;interaction=Date.now();
    if(e.key==='Enter'&&e.target instanceof HTMLInputElement) {
      const zone=e.target.form||e.target.closest('[role="form"]')||document;
      saisir(zone,zone.querySelector('button[type="submit"],input[type="submit"],button')?.textContent||'');
    }
  },options);
  document.addEventListener('submit',e=>{
    if(e.target instanceof HTMLFormElement&&Date.now()-interaction<2000)saisir(e.target,e.submitter?.textContent||'');
  },options);
  window.addEventListener('pagehide',()=>{dernierUtilisateur='';utilisateurExpire=0;resultatObserve?.disconnect();clearTimeout(resultatTimer);},options);
})();
