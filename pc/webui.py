"""Compact loopback dashboard for the running OpenBuddy event bridge."""

import webbrowser

PAGE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenBuddy — tableau de bord</title>
  <style>
    :root { color-scheme: dark; font: 14px/1.35 system-ui, sans-serif; background: #10131b; color: #edf2ff; }
    * { box-sizing: border-box; }
    body { max-width: 1120px; margin: 0 auto; padding: 12px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
    h1 { font-size: 1.35rem; margin: 0; } h2 { font-size: 1rem; margin: 0 0 8px; }
    p { margin: 6px 0; } .muted { color: #aab4ca; font-size: .88rem; }
    .pill { border: 1px solid #46516a; border-radius: 999px; padding: 4px 10px; white-space: nowrap; }
    .layout { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(300px, .9fr); gap: 10px; align-items: start; }
    .stack { display: grid; gap: 10px; }
    .card { background: #1b2130; border: 1px solid #30394d; border-radius: 11px; padding: 12px; }
    .live-content { display: grid; grid-template-columns: minmax(0, 1fr) 155px; gap: 8px; align-items: center; }
    .status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
    .status-cell { background: #141a25; border-radius: 8px; padding: 8px; min-width: 0; }
    .value { font-weight: 700; overflow-wrap: anywhere; }
    .states { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; margin-top: 7px; }
    button { border: 0; border-radius: 7px; padding: 8px; background: #536dfe; color: white; font: inherit; font-weight: 650; cursor: pointer; }
    button.mini { padding: 3px 7px; font-size: .78rem; }
    button:hover { filter: brightness(1.13); } button:disabled { opacity: .46; cursor: not-allowed; }
    button.secondary { background: #414b61; }
    input { border-radius: 7px; border: 1px solid #46516a; background: #111722; color: inherit; font: inherit; padding: 6px; }
    input[type=number] { width: 76px; }
    .controls { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
    .controls label { display: flex; align-items: center; gap: 6px; }
    .web-preview { display: grid; grid-template-columns: 1fr; justify-items: center; gap: 4px; background: #141a25; padding: 7px; border-radius: 8px; text-align: center; }
    #preview-pet { width: 100%; max-width: 150px; }
    #pet-canvas { width: 70px; height: auto; image-rendering: pixelated; background: #080c14; border-radius: 5px; }
    .pet-list { display: grid; gap: 6px; }
    .pet-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; background: #141a25; border-radius: 8px; padding: 7px 8px; }
    .pet-meta { min-width: 0; } .pet-title { font-weight: 700; overflow-wrap: anywhere; }
    .pet-actions { display: flex; flex: 0 0 auto; gap: 4px; }
    .pet-row button { min-width: 72px; padding: 7px 5px; }
    .active { color: #8fe1ad; font-size: .8rem; }
    #message { min-height: 1.2em; } .error { color: #ff8e9b; } .ok { color: #8fe1ad; }
    .timer { color: #ffd166; font-variant-numeric: tabular-nums; }
    @media (max-width: 760px) { .layout { grid-template-columns: 1fr; } }
    @media (max-width: 480px) { .live-content { grid-template-columns: 1fr; } .web-preview { grid-template-columns: auto 1fr; text-align: left; } #preview-pet { grid-column: 2; } #pet-canvas { grid-row: 1 / span 2; } }
    @media (max-width: 430px) { .states { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  </style>
</head>
<body>
  <header><h1>OpenBuddy</h1><span id="connection" class="pill">Connexion…</span></header>
  <main class="layout">
    <div class="stack">
      <section class="card">
        <h2>État en direct</h2>
        <div class="live-content">
          <div class="status-grid">
            <div class="status-cell"><div class="muted">OpenCode</div><div class="value" id="opencode-state">—</div></div>
            <div class="status-cell"><div class="muted">Affiché sur le pet</div><div class="value" id="display-state">—</div></div>
            <div class="status-cell"><div class="controls"><div class="muted">Pet sur l’ESP32</div><button class="mini" id="pet-next" disabled>Suivant</button></div><div class="value" id="active-pet">—</div></div>
            <div class="status-cell"><div class="muted">microSD</div><div class="value" id="sd-state">—</div></div>
          </div>
          <div class="web-preview">
            <div class="muted">Pet affiché sur le web</div>
            <select id="preview-pet" aria-label="Pet affiché dans l’aperçu web"></select>
            <canvas id="pet-canvas" width="96" height="104"></canvas>
            <div class="value" id="preview-name">Choisis un pet local</div>
            <div class="muted">Indépendant de l’ESP32</div>
          </div>
        </div>
        <div id="override-status" class="timer"></div>
        <div id="message" role="status" class="muted"></div>
      </section>
      <section class="card">
        <h2>Aperçu temporaire</h2>
        <div class="controls">
          <label>Durée <input id="duration" type="number" min="1" max="3600" step="1" value="15"> s</label>
          <label>Libellé <input id="label" maxlength="24" placeholder="Test manuel"></label>
          <button class="secondary" id="clear" disabled>Annuler l’aperçu</button>
        </div>
        <div class="states" id="states"></div>
        <div class="muted">Retour automatique à l’état OpenCode à la fin. Aucun outil ni aucune permission ne sont déclenchés.</div>
      </section>
    </div>
    <section class="card">
      <h2>Pets disponibles localement</h2>
      <div id="sd-hint" class="muted">Recherche des packs…</div>
      <div id="pets" class="pet-list"></div>
      <div class="muted">Installer copie et vérifie le pack ; Activer sélectionne un pack déjà sur la SD. Aucun formatage ni effacement des autres packs.</div>
    </section>
  </main>
  <script>
    const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
    history.replaceState(null, '', location.pathname);
    const labels = {idle:'Prêt', thinking:'Réflexion', working:'En cours', permission:'Autorisation', question:'Question', success:'Succès', error:'Erreur', retry:'Nouvel essai'};
    const message = document.querySelector('#message');
    const stateButtons = document.querySelector('#states');
    let usbConnected = false, deviceConnected = false, sdReady = false, manualActive = false, busy = false;
    let localCatalogLoaded = false;
    let previewTimer = null, previewRequest = 0, previewKey = null, webPreviewPet = null, currentPreviewState = 'offline';
    const previewCache = new Map();
    async function api(path, options = {}) {
      const headers = {...(options.headers || {}), 'Authorization':'Bearer ' + token};
      if (options.body !== undefined) headers['Content-Type'] = 'application/json';
      const response = await fetch(path, {...options, headers});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Erreur HTTP ' + response.status);
      return result;
    }
    function stateText(view) {
      if (!view) return 'Aucun état récent';
      return (labels[view.state] || view.state) + (view.label ? ' — ' + view.label : '');
    }
    function setBusy(value) { busy = value; updateButtons(); }
    function updateButtons() {
      document.querySelectorAll('.states button').forEach(button => button.disabled = busy || !deviceConnected);
      document.querySelectorAll('[data-install]').forEach(button => button.disabled = busy || !usbConnected || !sdReady);
      document.querySelectorAll('[data-activate]').forEach(button => button.disabled = busy || !usbConnected || !sdReady || button.dataset.activate === activeDevicePet);
      document.querySelector('#pet-next').disabled = busy || !usbConnected;
      document.querySelector('#clear').disabled = busy || !manualActive;
    }
    function showError(error) { message.textContent = error.message; message.className = 'error'; }
    function drawPetFrame(raw) {
      const canvas = document.querySelector('#pet-canvas');
      const context = canvas.getContext('2d');
      const image = context.createImageData(canvas.width, canvas.height);
      for (let source = 0, target = 0; source + 1 < raw.length; source += 2, target += 4) {
        const color = (raw[source] << 8) | raw[source + 1];
        const red = (color >> 11) & 31, green = (color >> 5) & 63, blue = color & 31;
        image.data[target] = (red << 3) | (red >> 2);
        image.data[target + 1] = (green << 2) | (green >> 4);
        image.data[target + 2] = (blue << 3) | (blue >> 2);
        image.data[target + 3] = 255;
      }
      context.putImageData(image, 0, 0);
    }
    async function showPet(id, state = currentPreviewState, persist = true) {
      const key = id ? id + ':' + state : null;
      if (persist && id) { try { localStorage.setItem('openbuddy-web-preview-pet', id); } catch (_) {} }
      if (key && key === previewKey) return;
      const request = ++previewRequest;
      if (previewTimer) clearInterval(previewTimer);
      previewTimer = null;
      const canvas = document.querySelector('#pet-canvas');
      const context = canvas.getContext('2d');
      previewKey = key;
      webPreviewPet = id || null;
      document.querySelector('#preview-name').textContent = id || 'Aucun pack local';
      if (!id) { context.clearRect(0, 0, canvas.width, canvas.height); return; }
      try {
        let preview = previewCache.get(key);
        if (!preview) {
          preview = await api('/pet-preview/' + encodeURIComponent(id) + '/' + encodeURIComponent(state));
          previewCache.set(key, preview);
          if (previewCache.size > 8) previewCache.delete(previewCache.keys().next().value);
        }
        if (request !== previewRequest) return;
        canvas.width = preview.width; canvas.height = preview.height;
        const frames = preview.frames.map(frame => Uint8Array.from(atob(frame), char => char.charCodeAt(0)));
        let frameIndex = 0;
        drawPetFrame(frames[frameIndex]);
        if (frames.length > 1) previewTimer = setInterval(() => { frameIndex = (frameIndex + 1) % frames.length; drawPetFrame(frames[frameIndex]); }, preview.frame_ms);
        document.querySelector('#preview-name').textContent = id.replaceAll('-', ' ') + ' · ' + (labels[state] || state);
      } catch (_) {
        if (request !== previewRequest) return;
        context.clearRect(0, 0, canvas.width, canvas.height);
        previewKey = null;
        document.querySelector('#preview-name').textContent = id + ' — aperçu indisponible';
      }
    }
    let activeDevicePet = null;
    async function refreshHealth() {
      const health = await api('/health');
      document.querySelector('#opencode-state').textContent = stateText(health.state);
      document.querySelector('#display-state').textContent = stateText(health.display_state);
      document.querySelector('#active-pet').textContent = health.pet || 'Robot de secours';
      const activePetChanged = activeDevicePet !== (health.pet || null);
      activeDevicePet = health.pet || null;
      document.querySelector('#sd-state').textContent = health.sd ? 'Prête' : 'Non détectée';
      usbConnected = Boolean(health.usb_connected);
      deviceConnected = usbConnected || Boolean(health.ble_connected);
      sdReady = Boolean(health.sd);
      const connection = document.querySelector('#connection');
      connection.textContent = usbConnected ? 'USB connecté' : health.ble_connected ? 'Bluetooth connecté' : 'Périphérique déconnecté';
      const override = health.manual_override;
      manualActive = Boolean(override);
      document.querySelector('#override-status').textContent = override ? 'Aperçu actif · retour dans ' + override.remaining_seconds + ' s' : '';
      currentPreviewState = health.display_state?.state || 'offline';
      if (webPreviewPet) await showPet(webPreviewPet, currentPreviewState, false);
      if (activePetChanged && localCatalogLoaded) {
        loadPets().catch(showError);
      }
      updateButtons();
    }
    async function loadPets() {
      const data = await api('/pets');
      sdReady = Boolean(data.sd);
      usbConnected = Boolean(data.usb_connected);
      localCatalogLoaded = true;
      const hint = document.querySelector('#sd-hint');
      hint.textContent = !data.sd ? 'Insère une microSD FAT32 pour activer l’installation.' : !data.usb_connected ? 'Reconnecte l’ESP32 en USB pour installer un pack.' : data.pets.length ? 'Packs RGB565 vérifiés et prêts à installer :' : 'Aucun pack valide dans build/pets/.';
      const list = document.querySelector('#pets');
      list.replaceChildren();
      for (const pet of data.pets) {
        const row = document.createElement('div'); row.className = 'pet-row';
        const meta = document.createElement('div'); meta.className = 'pet-meta';
        const title = document.createElement('div'); title.className = 'pet-title'; title.textContent = pet.name;
        const detail = document.createElement('div'); detail.className = 'muted'; detail.textContent = pet.animations + ' animations · ' + pet.frames + ' images · ' + (pet.size_bytes / 1048576).toFixed(1) + ' Mo';
        meta.append(title, detail);
        if (pet.active) { const active = document.createElement('div'); active.className = 'active'; active.textContent = 'Actif'; meta.append(active); }
        const actions = document.createElement('div'); actions.className = 'pet-actions';
        const install = document.createElement('button'); install.dataset.install = pet.id; install.textContent = pet.active ? 'Réinstaller' : 'Installer';
        install.addEventListener('click', () => installPet(pet.id, pet.name));
        const activate = document.createElement('button'); activate.dataset.activate = pet.id; activate.textContent = pet.active ? 'Actif' : 'Activer';
        activate.addEventListener('click', () => activatePet(pet.id, pet.name));
        const useWeb = document.createElement('button'); useWeb.dataset.preview = pet.id; useWeb.textContent = 'Aperçu web';
        useWeb.title = 'Afficher ce pet ici sans changer l’ESP32';
        useWeb.addEventListener('click', () => chooseWebPet(pet.id));
        actions.append(install, activate, useWeb); row.append(meta, actions); list.append(row);
      }
      const selector = document.querySelector('#preview-pet');
      const previous = selector.value;
      selector.replaceChildren();
      for (const pet of data.pets) {
        const option = document.createElement('option'); option.value = pet.id; option.textContent = pet.name;
        selector.append(option);
      }
      let selected = previous;
      if (!data.pets.some(pet => pet.id === selected)) {
        try { selected = localStorage.getItem('openbuddy-web-preview-pet'); } catch (_) { selected = null; }
      }
      if (!data.pets.some(pet => pet.id === selected)) selected = data.pets.find(pet => pet.active)?.id || data.pets[0]?.id || null;
      selector.value = selected || '';
        await showPet(selected, currentPreviewState, false);
      updateButtons();
    }
    function chooseWebPet(id) {
      const selector = document.querySelector('#preview-pet');
      selector.value = id;
      showPet(id, currentPreviewState);
    }
    async function inject(state) {
      const duration = Number(document.querySelector('#duration').value);
      if (!Number.isInteger(duration) || duration < 1 || duration > 3600) { showError(new Error('Durée autorisée : 1 à 3600 secondes.')); return; }
      setBusy(true);
      try { const result = await api('/manual-state', {method:'POST', body:JSON.stringify({state, duration, label:document.querySelector('#label').value})}); message.textContent = 'Aperçu « ' + labels[state] + ' » actif ' + result.duration + ' s.'; message.className = 'ok'; await refreshHealth(); }
      catch (error) { showError(error); }
      finally { setBusy(false); }
    }
    async function installPet(id, name) {
      if (!sdReady) { showError(new Error('La carte SD n’est pas détectée.')); return; }
      setBusy(true); message.textContent = 'Installation de ' + name + '…'; message.className = 'muted';
      try {
        await api('/pets/install', {method:'POST', body:JSON.stringify({pet:id})});
        message.textContent = name + ' installé, vérifié et activé sur la SD.'; message.className = 'ok';
        await refreshHealth(); await loadPets();
      } catch (error) { showError(error); }
      finally { setBusy(false); updateButtons(); }
    }
    async function activatePet(id, name) {
      if (!sdReady) { showError(new Error('La carte SD n’est pas détectée.')); return; }
      setBusy(true); message.textContent = 'Activation de ' + name + '…'; message.className = 'muted';
      try {
        await api('/pets/activate', {method:'POST', body:JSON.stringify({pet:id})});
        message.textContent = name + ' activé sur la SD.'; message.className = 'ok';
        await refreshHealth(); await loadPets();
      } catch (error) { showError(error); }
      finally { setBusy(false); updateButtons(); }
    }
    async function nextPet() {
      setBusy(true); message.textContent = 'Changement du pet…'; message.className = 'muted';
      try { await api('/pet/next', {method:'POST', body:'{}'}); await refreshHealth(); await loadPets(); message.textContent = 'Pet changé.'; message.className = 'ok'; }
      catch (error) { showError(error); }
      finally { setBusy(false); updateButtons(); }
    }
    for (const [state, label] of Object.entries(labels)) {
      const button = document.createElement('button'); button.textContent = label;
      button.addEventListener('click', () => inject(state)); stateButtons.append(button);
    }
    document.querySelector('#clear').addEventListener('click', async () => {
      setBusy(true);
      try { await api('/manual-state/clear', {method:'POST', body:'{}'}); message.textContent = 'Retour immédiat à OpenCode.'; message.className = 'ok'; await refreshHealth(); }
      catch (error) { showError(error); }
      finally { setBusy(false); }
    });
    document.querySelector('#pet-next').addEventListener('click', nextPet);
    document.querySelector('#preview-pet').addEventListener('change', event => chooseWebPet(event.target.value));
    Promise.all([refreshHealth(), loadPets()]).catch(showError);
    setInterval(() => refreshHealth().catch(showError), 1000);
  </script>
</body>
</html>
"""


def open_dashboard(url, token):
    return webbrowser.open(url + "#token=" + token)
