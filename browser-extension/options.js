const api = typeof browser !== 'undefined' ? browser : chrome;
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
  document.getElementById('status').textContent = 'Réglages enregistrés.';
};
