const gerado = JSON.parse(sessionStorage.getItem('gerado') || 'null');
const proposta = JSON.parse(sessionStorage.getItem('proposta') || 'null');

if (!gerado) {
  window.location.href = '/';
}

document.getElementById('pasta-path').textContent = gerado.pasta;

const filesList = document.getElementById('files-list');
(gerado.files ?? []).forEach(f => {
  const li = document.createElement('li');
  li.className = 'file-item';
  li.textContent = f;
  filesList.appendChild(li);
});

document.getElementById('primeiro-prompt').textContent =
  proposta?.primeiro_prompt ?? '';

if (gerado.launch_error) {
  const warn = document.getElementById('launch-warning');
  warn.textContent =
    `Claude Code não abriu automaticamente: ${gerado.launch_error}\n` +
    `Execute manualmente: cd ${gerado.pasta} && claude "${proposta?.primeiro_prompt ?? ''}"`;
  warn.className = 'status error';
}

document.getElementById('btn-novo').addEventListener('click', () => {
  sessionStorage.removeItem('proposta');
  sessionStorage.removeItem('gerado');
  window.location.href = '/';
});
