const api = typeof browser !== 'undefined' ? browser : chrome;
// Texts come from _locales/<language>/messages.json; the HTML holds the English fallback.
const message = (key) => api.i18n.getMessage(key);
document.documentElement.lang = api.i18n.getUILanguage();
for (const element of document.querySelectorAll('[data-i18n]')) {
  element.textContent = message(element.dataset.i18n) || element.textContent;
}
for (const element of document.querySelectorAll('[data-i18n-placeholder]')) {
  element.placeholder = message(element.dataset.i18nPlaceholder) || element.placeholder;
}
api.storage.local.get(['token', 'port']).then(({token, port}) => {
  document.getElementById('token').value = token || '';
  document.getElementById('port').value = port || '';
});
document.getElementById('save').onclick = async () => {
  const port = Number.parseInt(document.getElementById('port').value, 10);
  await api.storage.local.set({
    token: document.getElementById('token').value.trim(),
    port: port >= 1024 && port <= 65535 ? port : null,
  });
  document.getElementById('status').textContent = message('saved') || 'Settings saved.';
};
