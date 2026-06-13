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

// ── Dispatcher: executar o plano task a task ─────────────────────────────────

const plano = proposta?.plano ?? [];
// Gate (#5): só recomendamos despachar quando a análise indicou orquestrar.
// Em projeto simples medimos o dispatcher custar MAIS — então avisamos e pedimos
// confirmação, sem bloquear (o usuário decide).
const recomendacao = proposta?.recomendacao;
const orquestrarOk = !recomendacao || recomendacao.orquestrar !== false;

if (plano.length) {
  document.getElementById('section-dispatch').classList.remove('hidden');
  if (!orquestrarOk) {
    const aviso = document.getElementById('dispatch-status');
    aviso.textContent =
      '⚠ ' + (recomendacao?.motivo || 'Projeto simples.') +
      ' O dispatcher tende a custar MAIS aqui — recomendado só para projetos grandes.';
    aviso.className = 'status';
    aviso.classList.remove('hidden');
  }
}

document.getElementById('btn-dispatch')?.addEventListener('click', async () => {
  const btn = document.getElementById('btn-dispatch');
  const status = document.getElementById('dispatch-status');
  const results = document.getElementById('dispatch-results');
  if (!orquestrarOk && !confirm(
    'Projeto simples: o dispatcher provavelmente custará mais que um prompt único ' +
    '(medido). Executar mesmo assim?'
  )) {
    return;
  }
  btn.disabled = true;
  results.innerHTML = '';
  status.textContent = `Executando ${plano.length} tasks (pode levar minutos)...`;
  status.className = 'status loading';
  try {
    const res = await fetch('/dispatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pasta: gerado.pasta, plano, skills: proposta?.skills ?? [] }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }
    // Stream NDJSON: uma linha por task (ao vivo) + uma linha de resumo.
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    let feitas = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const linha = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!linha) continue;
        const ev = JSON.parse(linha);
        if (ev.tipo === 'task') {
          feitas += 1;
          const ok = ev.ok === false ? '✗' : '✓';
          const agente = ev.agente ? ` · ${ev.agente}` : '';
          const custo = ev.cost_usd != null ? ` · $${ev.cost_usd}` : '';
          const testes = ev.testes_ok === false ? ' · testes ✗'
            : ev.testes_ok === true ? ' · testes ✓' : '';
          const li = document.createElement('li');
          li.className = 'file-item';
          li.textContent = `${ok} ${ev.ordem}. ${ev.task} [${ev.modelo}${agente}]${custo}${testes}`;
          results.appendChild(li);
          status.textContent = `Executando... ${feitas}/${plano.length} tasks`;
        } else if (ev.tipo === 'resumo') {
          status.textContent = `Plano executado · custo total ~$${ev.custo_usd_total}`;
          status.className = 'status';
        }
      }
    }
  } catch (err) {
    status.textContent = `Erro: ${err.message}`;
    status.className = 'status error';
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('btn-novo').addEventListener('click', () => {
  sessionStorage.removeItem('proposta');
  sessionStorage.removeItem('gerado');
  window.location.href = '/';
});
