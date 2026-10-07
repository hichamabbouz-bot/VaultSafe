const $=id=>document.getElementById(id), id=location.hash.slice(1);
let occupe=false, relire=false, oeilTimer, dossier='', compte='';
async function demander(action, extra={}) {
  const r=await chrome.runtime.sendMessage({action,id,...extra});
  if(!r?.ok)throw Error(r?.erreur||'Liaison VaultSafe indisponible.');return r;
}
function message(texte,erreur=false){$('message').textContent=texte;$('message').hidden=!texte;$('message').classList.toggle('erreur',erreur);}
function choix(cle,items,valeur,changer){
  const zone=$(cle);zone.replaceChildren();
  const b=document.createElement('button'),texte=document.createElement('span'),menu=document.createElement('div');
  b.type='button';b.setAttribute('aria-haspopup','menu');b.setAttribute('aria-expanded','false');
  texte.textContent=items.find(v=>v.id===valeur)?.nom||items[0].nom;b.append(texte,document.createTextNode('⌄'));
  menu.className='menu';menu.hidden=true;menu.setAttribute('role','menu');
  const fermer=()=>{menu.hidden=true;b.setAttribute('aria-expanded','false');};
  for(const item of items){const e=document.createElement('button');e.type='button';e.textContent=item.nom;
    e.setAttribute('role','menuitemradio');e.setAttribute('aria-checked',String(item.id===valeur));
    if(item.id===valeur)e.className='actif';
    e.onclick=()=>{changer(item.id);choix(cle,items,item.id,changer);$(cle).firstChild.focus();};menu.append(e);}
  b.onclick=()=>{for(const autre of document.querySelectorAll('.menu'))if(autre!==menu)autre.hidden=true;
    menu.hidden=!menu.hidden;b.setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden)menu.querySelector('.actif')?.focus();};
  zone.onkeydown=e=>{if(e.key==='Escape'){fermer();b.focus();}
    if(['ArrowDown','ArrowUp'].includes(e.key)&&!menu.hidden){e.preventDefault();const l=[...menu.children],n=l.indexOf(document.activeElement);l[(n+(e.key==='ArrowDown'?1:-1)+l.length)%l.length].focus();}};
  zone.append(b,menu);
}
async function lire(){
  const conserver=!$('formulaire').hidden;
  const r=await demander('capture_read');
  if(r.theme)document.documentElement.dataset.theme=r.theme;
  $('formulaire').hidden=true;$('ouvrir').hidden=true;
  if(r.origine)$('origine').textContent=new URL(r.origine).host;
  $('service').textContent=r.service||'Compte détecté';
  if(/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(r.icone||'')){
    const img=document.createElement('img');img.alt='';img.src=r.icone;$('logo').replaceChildren(img);
  }else $('logo').textContent=(r.service||'V').slice(0,1).toUpperCase();
  if(['enregistre','mis_a_jour','identique','ignore'].includes(r.etat)){
    $('mot').value='';$('ignorer').hidden=true;$('exclure').hidden=true;
    message(r.texte||'Proposition ignorée.');setTimeout(()=>demander('capture_close').catch(()=>{}),2200);return;
  }
  if(['verrouille','indisponible'].includes(r.etat)){
    message(r.erreur||(r.etat==='verrouille'?'Déverrouiller VaultSafe pour enregistrer.':'Liaison indisponible. Ouvrez VaultSafe et associez l’extension dans Paramètres.'));$('ouvrir').hidden=false;
    $('ouvrir').textContent=r.etat==='verrouille'?'Déverrouiller VaultSafe pour enregistrer':'Ouvrir VaultSafe puis réessayer';return;
  }
  $('formulaire').hidden=false;
  if(!conserver){$('utilisateur').value=r.utilisateur||'';$('mot').value=r.mot_de_passe||'';}
  r.mot_de_passe='';
  dossier=r.dossier||'';choix('dossier',[{id:'',nom:'Sans dossier'},...(r.dossiers||[])],dossier,v=>dossier=v);
  const candidats=r.candidats||[];compte=candidats.length===1?candidats[0].id:'';
  $('choix-compte').hidden=candidats.length<2;
  choix('compte',[{id:'',nom:'Choisir un compte'},...candidats.map(c=>({id:c.id,nom:c.utilisateur||c.titre}))],compte,v=>{
    compte=v;if(r.type==='changement'&&!r.utilisateur)$('utilisateur').value=candidats.find(c=>c.id===v)?.utilisateur||'';
  });
  $('sauver').textContent=candidats.length?'Mettre à jour':'Enregistrer';
  message(r.resultat==='echec'?'La connexion semble refusée. Vérifiez les champs avant d’enregistrer.':
    candidats.length?'Mot de passe différent · vérifiez la connexion.':'');
}
async function action(f){if(occupe)return;occupe=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{await f();}catch(e){message(e.message,true);if(/verrouill/i.test(e.message)){$('mot').value='';$('formulaire').hidden=true;$('ouvrir').hidden=false;}}finally{occupe=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);if(relire){relire=false;action(lire);}}}
$('oeil').onclick=()=>{
  clearTimeout(oeilTimer);$('mot').type=$('mot').type==='password'?'text':'password';
  $('oeil').setAttribute('aria-label',$('mot').type==='password'?'Afficher le mot de passe':'Masquer le mot de passe');
  if($('mot').type==='text')oeilTimer=setTimeout(()=>{$('mot').type='password';},10000);
};
$('sauver').onclick=e=>{if(!e.isTrusted)return;action(async()=>{
  if(!$('mot').value)throw Error('Le mot de passe est obligatoire.');
  const r=await demander('capture_save',{utilisateur:$('utilisateur').value,mot_de_passe:$('mot').value,dossier,compte});
  $('mot').value='';$('utilisateur').value='';$('formulaire').hidden=true;message(r.texte);$('ignorer').hidden=true;
  setTimeout(()=>demander('capture_close').catch(()=>{}),2000);
});};
for(const b of ['fermer','ignorer'])$(b).onclick=()=>action(async()=>{
  $('mot').value='';await demander('capture_ignore');await demander('capture_close');
});
$('exclure').onclick=()=>action(async()=>{await demander('capture_exclude');$('mot').value='';await demander('capture_close');});
$('ouvrir').onclick=()=>action(async()=>{await demander('capture_unlock');await lire();});
chrome.runtime.onMessage.addListener((m,s)=>{if(s.id===chrome.runtime.id&&m.action==='capture_refresh'&&m.id===id){if(occupe)relire=true;else action(lire);}});
document.addEventListener('click',e=>{for(const zone of document.querySelectorAll('.choix'))if(!zone.contains(e.target)){const menu=zone.querySelector('.menu');if(menu)menu.hidden=true;zone.firstChild?.setAttribute('aria-expanded','false');}});
addEventListener('pagehide',()=>{$('mot').value='';$('utilisateur').value='';clearTimeout(oeilTimer);});
setTimeout(()=>{$('mot').value='';$('utilisateur').value='';$('formulaire').hidden=true;message('Proposition expirée. Soumettez de nouveau le formulaire.');},120000);
action(lire);
new ResizeObserver(()=>demander('capture_resize',{hauteur:Math.ceil(document.body.getBoundingClientRect().height)+2}).catch(()=>{})).observe(document.body);
