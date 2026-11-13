// Configure the shared token (and port, if changed) in the extension's options before use.
const api = typeof browser !== 'undefined' ? browser : chrome;
const DEFAULT_PORT = 8765;

function browserProcess() {
  const agent = navigator.userAgent;
  if (/Firefox\//.test(agent)) return 'firefox.exe';
  if (/Edg\//.test(agent)) return 'msedge.exe';
  if (navigator.brave) return 'brave.exe';
  return 'chrome.exe';
}
const process = browserProcess();

async function sync() {
  try {
    const {token, port} = await api.storage.local.get(['token', 'port']);
    if (!token) return;
    const tabs = await api.tabs.query({active: true, lastFocusedWindow: true});
    const tabUrl = tabs[0]?.url || '';
    // Non-web pages (new tab, settings) clear the domain so no site profile lingers.
    const url = /^https?:\/\//.test(tabUrl) ? tabUrl : '';
    await fetch(`http://127.0.0.1:${port || DEFAULT_PORT}/active`, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-pawz-Token': token},
      body: JSON.stringify({process, url})
    });
  } catch (_) { /* Desktop app may be stopped. */ }
}
api.tabs.onActivated.addListener(sync);
api.tabs.onUpdated.addListener((_id, change) => { if (change.url || change.status) sync(); });
api.windows.onFocusChanged.addListener(sync);
// Heartbeat so a restarted desktop app learns the current tab; 30 s is the MV3 minimum.
api.alarms.create('sync', {periodInMinutes: 0.5});
api.alarms.onAlarm.addListener(sync);
sync();
