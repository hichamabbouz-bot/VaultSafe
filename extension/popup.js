import { utiliserMotGenere } from "./formulaires.js";
const $=id=>document.getElementById(id);
let onglet, fiches=[], ouvert=false, occupe=false, longueur=20, symboles=true;
let generation=0, minuteurIcone, minuteurOeil;
const chemins={
  globe:"M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z",
  oeil:"M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
  copie:"M9 9h11v11H9ZM15 9V4H4v11h5"
};
function icone(nom){
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg"),p=document.createElementNS(svg.namespaceURI,"path");
  svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("aria-hidden","true");p.setAttribute("d",chemins[nom]);svg.append(p);return svg;
}
function notifier(texte,type=""){const z=$("statut");z.textContent=texte;z.hidden=!texte;z.className=type;}
function page(id){
  for(const p of document.querySelectorAll(".page"))p.hidden=p.id!==id;
  for(const b of document.querySelectorAll("nav button")){b.classList.toggle("actif",b.dataset.page===id);b.setAttribute("aria-pressed",String(b.dataset.page===id));}
  notifier("");masquer();if(id==="generateur")generer();else $("genere").value="";
}
function masquer(){clearTimeout(minuteurOeil);$("genere").type="password";$("oeil").setAttribute("aria-label","Afficher le mot de passe");}
async function courant(){
  const [t]=await chrome.tabs.query({active:true,currentWindow:true});if(!t?.url||t.incognito)throw Error("Ouvrez un site HTTPS.");
  const u=new URL(t.url);
  if(u.username||u.password||(u.protocol!=="https:"&&!(u.protocol==="http:"&&["localhost","127.0.0.1","[::1]"].includes(u.hostname))))throw Error("Ouvrez un site HTTPS.");
  return t;
}
function contexte(){return{tabId:onglet.id,origine:new URL(onglet.url).origin};}
async function verifierOnglet(){
  const t=await courant();if(!onglet||t.id!==onglet.id||t.windowId!==onglet.windowId||new URL(t.url).origin!==new URL(onglet.url).origin)throw Error("Le site a changé. Actualisez l’extension.");return t;
}
async function demander(contenu){const r=await chrome.runtime.sendMessage(contenu);if(!r?.ok)throw Error(r?.erreur||"Ouvrez VaultSafe pour continuer.");return r;}
function afficherListe(){
  const mots=$("recherche").value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  const visibles=fiches.filter(f=>mots.every(m=>(f.titre+" "+f.utilisateur+" "+(f.dossier_nom||"")).toLocaleLowerCase().includes(m)));
  $("fiches").replaceChildren();$("recherche").hidden=fiches.length<6;$("aucun").hidden=visibles.length!==0;
  for(const f of visibles){
    const ligne=document.createElement("div"),resume=document.createElement("div"),titre=document.createElement("strong"),secondaire=document.createElement("small"),b=document.createElement("button");
    ligne.className="fiche";resume.className="resume";titre.textContent=f.utilisateur||f.titre;secondaire.textContent=f.titre;resume.append(titre,secondaire);
    b.className="principal";b.textContent="Remplir";b.addEventListener("click",e=>{if(e.isTrusted)action(async()=>{
      await verifierOnglet();notifier("Confirmez le remplissage dans VaultSafe.");
      await demander({action:"fill",...contexte(),id:f.id});notifier("Champs remplis.","succes");
    });});ligne.append(resume,b);$("fiches").append(ligne);
  }
}
function afficherIcone(valeur){
  if(typeof valeur!=="string"||valeur.length>100000||!/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(valeur))return false;
  const img=document.createElement("img");img.src=valeur;img.alt="";$("icone-site").replaceChildren(img);return true;
}
function attendreIcone(g,essai=0){
  minuteurIcone=setTimeout(async()=>{
    if(document.hidden||!ouvert||g!==generation)return;
    try{await verifierOnglet();const r=await demander({action:"list",...contexte()});if(g!==generation)return;
      if(!afficherIcone(r.icone)&&r.icone_en_attente&&essai<2)attendreIcone(g,essai+1);
    }catch{/* Arrêt au changement de contexte. */}
  },1500);
}
async function actualiser(){
  clearTimeout(minuteurIcone);const g=++generation;fiches=[];ouvert=false;
  $("comptes").hidden=true;$("indisponible").hidden=false;$("ouvrir").hidden=true;$("recherche").value="";$("icone-site").replaceChildren(icone("globe"));
  try{onglet=await courant();const u=new URL(onglet.url);$("service").textContent=u.hostname;$("hote").textContent=u.host;
    const r=await demander({action:"observe",...contexte()});if(!r.capture.active)notifier(r.capture.erreur,"erreur");
  }catch{onglet=null;$("service").textContent="Aucun site compatible";$("hote").textContent="";}
  let etat;
  try{etat=await demander({action:"status"});}catch{
    $("etat").textContent="Indisponible";$("etat").className="";$("message-etat").textContent="Ouvrez VaultSafe pour accéder aux comptes.";$("ouvrir").hidden=false;return;
  }
  if(["light","dark"].includes(etat.theme))document.documentElement.dataset.theme=etat.theme;
  ouvert=Boolean(etat.ouvert);$("etat").textContent=ouvert?"Connecté":"Verrouillé";$("etat").className=ouvert?"ouvert":"";
  if(!ouvert){$("message-etat").textContent="Déverrouillez VaultSafe pour remplir ce site.";$("ouvrir").hidden=false;return;}
  if(!onglet){$("message-etat").textContent="Le remplissage est disponible sur un site HTTPS.";return;}
  const resultat=await demander({action:"list",...contexte()});if(g!==generation)return;
  fiches=resultat.fiches||[];$("service").textContent=resultat.service||new URL(onglet.url).hostname;
  if(!afficherIcone(resultat.icone)&&resultat.icone_en_attente)attendreIcone(g);
  $("indisponible").hidden=true;$("comptes").hidden=false;afficherListe();
}
function aleatoire(n){const v=new Uint32Array(1),limite=Math.floor(4294967296/n)*n;do{crypto.getRandomValues(v);}while(v[0]>=limite);return v[0]%n;}
function generer(){
  masquer();const groupes=["abcdefghijkmnopqrstuvwxyz","ABCDEFGHJKLMNPQRSTUVWXYZ","23456789",...(symboles?["!#$%&*+-=?@_"]:[])],alphabet=groupes.join(""),mot=groupes.map(g=>g[aleatoire(g.length)]);
  while(mot.length<longueur)mot.push(alphabet[aleatoire(alphabet.length)]);
  for(let i=mot.length-1;i>0;i--){const j=aleatoire(i+1);[mot[i],mot[j]]=[mot[j],mot[i]];}
  $("genere").value=mot.join("");$("longueur").textContent=String(longueur);
}
async function utiliser(){
  const t=await verifierOnglet();
  const resultat=(await chrome.scripting.executeScript({target:{tabId:t.id,frameIds:[0]},func:utiliserMotGenere,args:[new URL(t.url).origin,$("genere").value]}))[0]?.result;
  if(!resultat?.ok)throw Error(resultat?.erreur||"Formulaire incompatible.");
  masquer();notifier("Mot de passe inséré.","succes");
}
function disponibilite(){ $("utiliser").disabled=occupe||!onglet; }
async function action(f){
  if(occupe)return;occupe=true;document.querySelectorAll("button").forEach(b=>b.disabled=true);
  try{await f();}catch(e){notifier(e.message||"Action impossible.","erreur");}
  finally{occupe=false;document.querySelectorAll("button").forEach(b=>b.disabled=false);disponibilite();}
}
function clic(id,f){$(id).addEventListener("click",e=>{if(e.isTrusted)action(f);});}
for(const b of document.querySelectorAll("nav button"))b.addEventListener("click",()=>{if(!occupe)page(b.dataset.page);});
$("recherche").addEventListener("input",afficherListe);
$("oeil").append(icone("oeil"));$("oeil").onclick=()=>{if($("genere").type==="text")masquer();else{$("genere").type="text";$("oeil").setAttribute("aria-label","Masquer le mot de passe");minuteurOeil=setTimeout(masquer,10000);}};
$("copier").append(icone("copie"));clic("copier",async()=>{if(!$("genere").value)return;await navigator.clipboard.writeText($("genere").value);notifier("Copié.","succes");});
clic("actualiser",actualiser);clic("ouvrir",async()=>{const r=await demander({action:"open"});await actualiser();if(!ouvert&&r.message)notifier(r.message);});
clic("moins",()=>{longueur=Math.max(12,longueur-1);generer();});clic("plus",()=>{longueur=Math.min(128,longueur+1);generer();});
clic("symboles",()=>{symboles=!symboles;$("symboles").setAttribute("aria-checked",String(symboles));generer();});
clic("regenerer",generer);clic("utiliser",utiliser);
addEventListener("pagehide",()=>{$("genere").value="";fiches=[];clearTimeout(minuteurIcone);masquer();});
action(actualiser);
