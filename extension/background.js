import { remplirChamps } from "./formulaires.js";
import { installerCaptures } from "./captures.js";

const hote = "org.vaultsafe.local";
const enCours = new Set();
const collecte = installerCaptures(demandeNative, activerCapture);
const pagesCapture = ['https://*/*', 'http://localhost/*', 'http://127.0.0.1/*', 'http://[::1]/*'];
async function activerCapture(tab) {
  try {
    const url = new URL(tab.url);
    if (tab.incognito || url.username || url.password || (url.protocol !== 'https:' &&
        !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))))
      return { active: false, erreur: 'Détection disponible sur HTTPS, hors navigation privée.' };
    const version = chrome.runtime.getManifest().version;
    const presente = async () => {
      const r = await chrome.tabs.sendMessage(tab.id, { action: 'capture_status' }, { frameId: 0 });
      return r?.ok && r.origine === url.origin && r.version === version;
    };
    try { if (await presente()) return { active: true }; } catch { /* Page ouverte avant la mise à jour. */ }
    await chrome.scripting.executeScript({ target: { tabId: tab.id, frameIds: [0] }, files: ['capture.js'] });
    if (await presente()) return { active: true };
    return { active: false, erreur: 'Le site a changé. Actualisez le popup.' };
  } catch {
    return { active: false, erreur: 'Autorisez l’accès à ce site dans les paramètres de l’extension, puis actualisez la page.' };
  }
}
async function activerPagesOuvertes() {
  const tabs = await chrome.tabs.query({ active: true, url: pagesCapture });
  await Promise.allSettled(tabs.map(activerCapture));
}
// Les déclarations statiques couvrent les nouvelles pages ; ces événements réparent les pages existantes.
chrome.runtime.onInstalled.addListener(() => { activerPagesOuvertes().catch(() => {}); });
chrome.runtime.onStartup.addListener(() => { activerPagesOuvertes().catch(() => {}); });
chrome.tabs.onActivated.addListener(({ tabId }) => {
  chrome.tabs.get(tabId).then(activerCapture).catch(() => {});
});
chrome.permissions.onAdded.addListener(() => { activerPagesOuvertes().catch(() => {}); });

function demandeNative(contenu) {
  return new Promise((resolve, reject) => {
    const port = chrome.runtime.connectNative(hote);
    let termine = false;
    const minuteur = setTimeout(() => finir(null, new Error("Confirmation expirée. Recommencez.")), 60000);
    function finir(reponse, erreur) {
      if (termine) return;
      termine = true;
      clearTimeout(minuteur);
      port.disconnect();
      if (erreur) reject(erreur); else resolve(reponse);
    }
    port.onMessage.addListener(reponse => {
      if (!reponse?.ok) finir(null, new Error(reponse?.erreur || "Action refusée par VaultSafe."));
      else finir(reponse);
    });
    port.onDisconnect.addListener(() => {
      const erreur = chrome.runtime.lastError;
      if (!termine) finir(null, new Error(erreur?.message || "Ouvrez VaultSafe et associez l’extension dans Paramètres."));
    });
    port.postMessage(contenu);
  });
}
async function onglet(id) {
  if (!Number.isInteger(id)) throw new Error("Onglet invalide.");
  const tab = await chrome.tabs.get(id);
  if (!tab.active || !tab.url || !/^https?:\/\//.test(tab.url)) throw new Error("Ouvrez l’extension sur le site souhaité.");
  const url = new URL(tab.url);
  if (url.username || url.password) throw new Error("Adresse contenant des identifiants refusée.");
  return tab;
}
async function traiter(message) {
  if (!message || !["status", "open", "observe", "list", "fill"].includes(message.action))
    throw new Error("Demande d’extension invalide.");
  if (["status", "open"].includes(message.action)) return demandeNative({ action: message.action });
  const tab = await onglet(message.tabId);
  const origine = new URL(tab.url).origin;
  if (message.origine !== origine) throw new Error("Le site a changé. Actualisez l’extension.");
  if (message.action === "observe") return { ok: true, capture: await activerCapture(tab) };
  if (message.action === "list") return demandeNative({ action: "list", url: tab.url });
  if (enCours.has(tab.id)) throw new Error("Une confirmation est déjà en attente pour cet onglet.");
  enCours.add(tab.id);
  try {
    const reponse = await demandeNative({ action: "fill", url: tab.url, id: message.id });
    try {
      if (!(await demandeNative({ action: "status" })).ouvert) throw new Error("VaultSafe a été verrouillé. Aucun remplissage effectué.");
      const apres = await onglet(tab.id);
      if (new URL(apres.url).origin !== origine || apres.windowId !== tab.windowId)
        throw new Error("L’onglet a changé. Aucun remplissage effectué.");
      const resultats = await chrome.scripting.executeScript({ target: { tabId: tab.id, frameIds: [0] },
        func: remplirChamps, args: [origine, reponse.utilisateur, reponse.mot_de_passe] });
      if (!resultats[0]?.result?.ok) throw new Error(resultats[0]?.result?.erreur || "Formulaire incompatible.");
      return { ok: true };
    } finally { reponse.mot_de_passe = ""; reponse.utilisateur = ""; }
  } finally { enCours.delete(tab.id); }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (collecte.accepte(message?.action)) {
    collecte.traiter(message, sender).then(sendResponse).catch(erreur =>
      sendResponse({ok:false, erreur:erreur.message || 'Enregistrement indisponible.'}));
    return true;
  }
  if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL("popup.html")) {
    sendResponse({ ok: false, erreur: "Demande d’extension non autorisée." });
    return false;
  }
  traiter(message).then(sendResponse).catch(erreur =>
    sendResponse({ ok: false, erreur: erreur.message || "Action impossible." }));
  return true;
});
