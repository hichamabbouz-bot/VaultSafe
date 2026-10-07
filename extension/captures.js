// Panneau chrome-extension:// : aucune donnée secrète dans le DOM du site ou storage.
export function installerCaptures(native, activer) {
  const cle='capture-tab-', login='login-', duree=120000, volatils=new Map(), minuteries=new Map(), enCours=new Set();
  let politique={mode:'proposition',exclus:[]};
  chrome.storage.local.get('capture-options').then(r=>{if(r['capture-options'])politique=r['capture-options'];});
  const final=r=>['identique','enregistre','mis_a_jour','ignore'].includes(r.etat);
  async function options(force=false) {
    if(force){const r=await native({action:'capture_options'});await memoriserOptions(r.options);}
    return politique;
  }
  async function memoriserOptions(p){
    if(!p||!['proposition','automatique','desactive'].includes(p.mode)||!Array.isArray(p.exclus))throw Error('Options invalides.');
    politique={mode:p.mode,exclus:p.exclus};await chrome.storage.local.set({'capture-options':politique});
    const tabs=await chrome.tabs.query({url:['https://*/*','http://localhost/*','http://127.0.0.1/*','http://[::1]/*']});
    await Promise.allSettled(tabs.map(t=>chrome.tabs.sendMessage(t.id,{action:'capture_policy_update',options:politique},{frameId:0})));
  }
  async function lire(tabId){
    const r=(await chrome.storage.session.get(cle+tabId))[cle+tabId];
    if(r&&r.expiration>Date.now())return r;
    if(r)await nettoyer(r);return null;
  }
  async function stocker(r){
    const tous=await chrome.storage.session.get(null);
    const actuel=tous[cle+r.tabId];
    if(actuel&&actuel.id!==r.id&&actuel.date>r.date)return false;
    const anciennes=Object.keys(tous).filter(k=>k.startsWith(cle)&&k!==cle+r.tabId).sort((a,b)=>tous[b].expiration-tous[a].expiration);
    for(const k of anciennes.filter((k,i)=>i>=7||tous[k].expiration<=Date.now()))await nettoyer(tous[k]);
    await chrome.storage.session.set({[cle+r.tabId]:r});
    return true;
  }
  async function nettoyer(r){
    clearTimeout(minuteries.get(r.id));minuteries.delete(r.id);
    const mem=volatils.get(r.id);if(mem){mem.mot_de_passe='';mem.utilisateur='';volatils.delete(r.id);}
    const actuel=(await chrome.storage.session.get(cle+r.tabId))[cle+r.tabId];
    if(actuel?.id===r.id)await chrome.storage.session.remove(cle+r.tabId);
    if(r.token)native({action:'capture_ignore',token:r.token}).catch(()=>{});
    chrome.tabs.sendMessage(r.tabId,{action:'capture_close',id:r.id},{frameId:0}).catch(()=>{});
    chrome.action.setBadgeText({tabId:r.tabId,text:''}).catch(()=>{});
  }
  async function afficher(r){
    // Une navigation peut finir avant capture_begin : attendre les champs du coffre.
    if(!r.retour)return;
    // L'automatique attend le résultat en arrière-plan, sans ouvrir le formulaire.
    if(r.automatique&&!r.termine)return;
    if((await lire(r.tabId))?.id!==r.id)return;
    const tab=await chrome.tabs.get(r.tabId);
    if(!tab.active||tab.incognito||tab.windowId!==r.windowId||new URL(tab.url).protocol!=='https:'&&
        !['localhost','127.0.0.1','[::1]'].includes(new URL(tab.url).hostname))return;
    await activer(tab);
    if((await lire(r.tabId))?.id!==r.id)return;
    await chrome.tabs.sendMessage(r.tabId,{action:'capture_panel',id:r.id},{frameId:0});
  }
  async function retour(r,reponse){
    if(['identique','ignore'].includes(reponse.etat)){await nettoyer(r);return;}
    // Cette copie ne contient que le résultat public, jamais les champs ni les candidats.
    r.retour={etat:reponse.etat,texte:reponse.texte,erreur:reponse.erreur,origine:r.origine,service:reponse.service,theme:reponse.theme,icone:reponse.icone};
    if(final(reponse)){r.termine=true;r.token='';volatils.delete(r.id);}
    else r.automatique=false;
    if(!await stocker(r))return;
    await chrome.action.setBadgeText({tabId:r.tabId,text:final(reponse)?'':reponse.etat==='indisponible'?'!':'+'});
    await afficher(r);
    chrome.tabs.sendMessage(r.tabId,{action:'capture_refresh',id:r.id}).catch(()=>{});
  }
  async function source(message,sender){
    if(sender.id!==chrome.runtime.id||sender.frameId!==0||!sender.tab||sender.tab.incognito)throw Error('Source de formulaire refusée.');
    const u=new URL(sender.url);
    if(u.username||u.password||u.origin!==message.origine||(u.protocol!=='https:'&&!(u.protocol==='http:'&&
        ['localhost','127.0.0.1','[::1]'].includes(u.hostname))))throw Error('Origine refusée.');
    const tab=await chrome.tabs.get(sender.tab.id);
    if(!tab.active||tab.windowId!==sender.tab.windowId)throw Error('Onglet inactif.');return{tab,u};
  }
  async function resoudre(r){
    if(!r.token||r.termine||r.expiration<=Date.now())return;
    const reponse=await native({action:'capture_resolve',token:r.token,resultat:r.resultat||'incertain'});
    await retour(r,reponse);
  }
  async function commencer(r,contenu){
    const rep=await native(contenu);
    const frais=await lire(r.tabId);if(frais?.id===r.id)r.resultat=frais.resultat;
    if(rep.options)await memoriserOptions(rep.options);
    r.token=rep.token||'';r.automatique=Boolean(rep.automatique);r.retour={etat:rep.etat,texte:rep.texte,origine:r.origine,service:rep.service,theme:rep.theme,icone:rep.icone};
    if(rep.etat==='ignore'&&!rep.token){await nettoyer(r);return;}
    if(final(rep)){await retour(r,rep);return;}
    await stocker(r);
    if(r.resultat==='echec'){await retour(r,await native({action:'capture_resolve',token:r.token,resultat:'echec'}));}
    else if(rep.automatique){
      // Laisser les erreurs visibles de la réponse remonter. Une mise à jour ne passe jamais ici.
      setTimeout(async()=>{try{const frais=await lire(r.tabId);if(frais?.id===r.id)await resoudre(frais);}catch{r.retour={etat:'indisponible',origine:r.origine};await retour(r,r.retour);}},3500);
    }else await retour(r,rep);
  }
  async function collecter(message,sender){
    const {tab,u}=await source(message,sender);
    if(message.action==='capture_policy'){
      try{return{ok:true,options:await options(true)};}catch{return{ok:true,options:await options()};}
    }
    if(message.action==='capture_result'){
      const r=await lire(tab.id);
      if(r&&r.origine===u.origin&&r.soumission===message.soumission&&!r.termine&&message.resultat==='echec'){
        r.resultat='echec';await stocker(r);
        if(r.token)await retour(r,await native({action:'capture_resolve',token:r.token,resultat:'echec'}));
      }
      return{ok:true};
    }
    if(typeof message.utilisateur!=='string'||message.utilisateur.length>200)throw Error('Identifiant invalide.');
    if(politique.mode==='desactive'||politique.exclus.includes(u.origin))return{ok:true,ignore:true};
    if(message.action==='login_step'){
      const tous=await chrome.storage.session.get(null),ks=Object.keys(tous).filter(k=>k.startsWith(login)).sort((a,b)=>tous[b].date-tous[a].date);
      await chrome.storage.session.remove(ks.filter((k,i)=>i>=7||Date.now()-tous[k].date>120000));
      await chrome.storage.session.set({[login+tab.id]:{origine:u.origin,utilisateur:message.utilisateur,date:Date.now()}});return{ok:true};
    }
    if(typeof message.soumission!=='string'||!/^[0-9a-f-]{36}$/.test(message.soumission)||
        typeof message.mot_de_passe!=='string'||!message.mot_de_passe||message.mot_de_passe.length>4096||
        !['connexion','inscription','changement'].includes(message.type)||typeof message.url!=='string'||new URL(message.url).origin!==u.origin)
      throw Error('Compte invalide.');
    if(enCours.has(tab.id))return{ok:true,ignore:true};
    const existant=await lire(tab.id);
    if(existant&&!existant.termine&&Date.now()-existant.date<1800)return{ok:true,ignore:true};
    enCours.add(tab.id);
    try{
      if(existant)await nettoyer(existant);
      const etape=(await chrome.storage.session.get(login+tab.id))[login+tab.id];
      const utilisateur=message.utilisateur||(etape&&etape.origine===u.origin&&Date.now()-etape.date<120000?etape.utilisateur:'');
      await chrome.storage.session.remove(login+tab.id);
      const r={id:crypto.randomUUID(),soumission:message.soumission,tabId:tab.id,windowId:tab.windowId,origine:u.origin,date:Date.now(),expiration:Date.now()+duree,resultat:'incertain'};
      const contenu={action:'capture_begin',url:message.url,utilisateur,mot_de_passe:message.mot_de_passe,type:message.type};
      minuteries.set(r.id,setTimeout(()=>nettoyer(r).catch(()=>{}),duree));
      await stocker(r);
      try{await commencer(r,contenu);contenu.mot_de_passe='';contenu.utilisateur='';}
      catch(e){
        // Seulement en RAM lorsque la liaison n'existe pas ; effacement au plus tard à deux minutes.
        volatils.set(r.id,contenu);await retour(r,{etat:'indisponible',erreur:e.message});
      }
      return{ok:true};
    }finally{enCours.delete(tab.id);message.mot_de_passe='';message.utilisateur='';}
  }
  async function cadre(message,sender){
    if(sender.id!==chrome.runtime.id||sender.url?.split('#')[0]!==chrome.runtime.getURL('capture-panel.html')||!sender.tab||sender.frameId===0)
      throw Error('Panneau non autorisé.');
    const r=await lire(sender.tab.id);
    if(!r||r.id!==message.id||sender.url.split('#')[1]!==r.id||r.windowId!==sender.tab.windowId)throw Error('Proposition expirée.');
    const tab=await chrome.tabs.get(r.tabId);if(!tab.active||tab.incognito)throw Error('Onglet inactif.');
    if(message.action==='capture_resize'){
      if(Number.isFinite(message.hauteur)&&message.hauteur>=100&&message.hauteur<=600)
        await chrome.tabs.sendMessage(r.tabId,{action:'capture_resize',id:r.id,hauteur:Math.ceil(message.hauteur)},{frameId:0});
      return{ok:true};
    }
    // Un retour public ne contient aucun secret et ne nécessite pas un formulaire visible.
    if(message.action==='capture_read'&&(r.termine||!r.token))return{ok:true,...r.retour};
    if(['capture_read','capture_save'].includes(message.action)){
      const visible=await chrome.tabs.sendMessage(r.tabId,{action:'capture_panel_valid',id:r.id},{frameId:0});
      if(!visible?.ok)throw Error('Le panneau doit être visible pour enregistrer.');
    }
    if(message.action==='capture_close'){await nettoyer(r);return{ok:true};}
    if(message.action==='capture_ignore'){if(r.token)await native({action:'capture_ignore',token:r.token});r.termine=true;r.token='';return{ok:true};}
    if(message.action==='capture_exclude'){
      const p=await options(true);const rep=await native({action:'capture_config',mode:p.mode,exclus:[...p.exclus,r.origine].join('\n')});
      await memoriserOptions(rep.options);await nettoyer(r);return{ok:true};
    }
    if(message.action==='capture_unlock'){
      const etat=await native({action:'open'});
      if(!etat.ouvert)throw Error(etat.message||'Déverrouillez VaultSafe dans la fenêtre Windows, puis réessayez.');
      const attente=volatils.get(r.id);
      if(attente){await commencer(r,attente);attente.mot_de_passe='';attente.utilisateur='';volatils.delete(r.id);}
      return{ok:true};
    }
    if(message.action==='capture_read'){
      if(r.termine||!r.token)return{ok:true,...r.retour};
      const rep=await native({action:'capture_read',token:r.token});
      if(final(rep))await retour(r,rep);return rep;
    }
    if(message.action==='capture_save'){
      const rep=await native({action:'capture_commit',token:r.token,utilisateur:message.utilisateur,mot_de_passe:message.mot_de_passe,
        dossier:message.dossier||'',id:message.compte||''});
      if(final(rep)){r.termine=true;r.token='';r.retour={etat:rep.etat,texte:rep.texte};await stocker(r);}
      await chrome.action.setBadgeText({tabId:r.tabId,text:''});return rep;
    }
    throw Error('Action de panneau invalide.');
  }
  chrome.tabs.onUpdated.addListener((tabId,change,tab)=>{
    if(change.status==='complete')lire(tabId).then(async r=>{if(r&&(Date.now()-r.date<15000||new URL(tab.url).origin===r.origine))await afficher(r);}).catch(()=>{});
  });
  chrome.tabs.onRemoved.addListener(tabId=>{lire(tabId).then(r=>r&&nettoyer(r)).catch(()=>{});chrome.storage.session.remove(login+tabId);});
  return{
    accepte:action=>['capture','login_step','capture_policy','capture_result','capture_read','capture_save','capture_ignore','capture_exclude','capture_unlock','capture_close','capture_resize','capture_options','capture_config'].includes(action),
    async traiter(message,sender){
      try{
        if(['capture','login_step','capture_policy','capture_result'].includes(message.action))return await collecter(message,sender);
        if(['capture_options','capture_config'].includes(message.action)){
          if(sender.id!==chrome.runtime.id||sender.url!==chrome.runtime.getURL('popup.html'))throw Error('Options non autorisées.');
          if(message.action==='capture_options')return{ok:true,options:await options(true)};
          const rep=await native({action:'capture_config',mode:message.mode,exclus:message.exclus});await memoriserOptions(rep.options);return rep;
        }
        return await cadre(message,sender);
      }finally{message.mot_de_passe='';message.utilisateur='';}
    }
  };
}
