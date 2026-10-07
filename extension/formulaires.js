// Fonctions autonomes : elles s'exécutent exclusivement dans le cadre principal du site.
export function remplirChamps(origineAttendue, utilisateur, motDePasse) {
  if (window.top !== window || location.origin !== origineAttendue) {
    return { ok: false, erreur: "Le site a changé. Recommencez depuis l’extension." };
  }
  const visible = element => {
    const style = getComputedStyle(element);
    return !element.disabled && !element.readOnly && !element.closest('[hidden],[inert],[aria-hidden="true"]') &&
      element.getClientRects().length > 0 &&
      style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity) > 0;
  };
  const mots = [...document.querySelectorAll('input[type="password"]')]
    .filter(element => visible(element) && element.autocomplete !== "new-password");
  if (mots.length !== 1) {
    return { ok: false, erreur: "Choisissez une page contenant un seul formulaire de connexion visible." };
  }
  const mot = mots[0];
  if (mot.form && new URL(mot.form.action || location.href, location.href).origin !== origineAttendue) {
    return { ok: false, erreur: "Le formulaire envoie ses données à un autre site. Remplissage refusé." };
  }
  const zone = mot.form || document;
  const candidats = [...zone.querySelectorAll('input:not([type]), input[type="text"], input[type="email"]')]
    .filter(visible);
  const noms = candidats.filter(element => /(?:^|\s)(username|email)(?:\s|$)/i.test(element.autocomplete) ||
    /user|login|email|mail|identifiant/i.test(element.name + " " + element.id));
  const login = noms.length === 1 ? noms[0] : candidats.length === 1 ? candidats[0] : null;
  if (utilisateur && !login) {
    return { ok: false, erreur: "Le champ utilisateur est ambigu. Aucun secret n’a été rempli." };
  }
  // Utiliser le setter natif pour les formulaires React/Vue ; aucun envoi automatique.
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  const definir = (element, valeur) => {
    setter.call(element, valeur);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };
  if (login && utilisateur) definir(login, utilisateur);
  definir(mot, motDePasse);
  return { ok: true };
}


export function utiliserMotGenere(origineAttendue, motDePasse) {
  if (window.top !== window || location.origin !== origineAttendue) return { ok: false, erreur: "Le site a changé." };
  const visible = e => !e.disabled && !e.readOnly && !e.closest('[hidden],[inert],[aria-hidden="true"]') &&
    e.getClientRects().length &&
    getComputedStyle(e).visibility !== "hidden" && getComputedStyle(e).display !== "none";
  const mots = [...document.querySelectorAll('input[type="password"]')].filter(visible);
  if (!mots.length || mots.length > 2 || (mots.length === 2 &&
      (!mots[0].form || mots[0].form !== mots[1].form))) return { ok: false, erreur: "Formulaire de mot de passe ambigu." };
  if (mots.some(e => e.form && new URL(e.form.action || location.href, location.href).origin !== origineAttendue))
    return { ok: false, erreur: "Le formulaire envoie ses données à un autre site." };
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  for (const e of mots) {
    setter.call(e, motDePasse);
    e.dispatchEvent(new Event("input", { bubbles: true }));
    e.dispatchEvent(new Event("change", { bubbles: true }));
  }
  return { ok: true };
}
