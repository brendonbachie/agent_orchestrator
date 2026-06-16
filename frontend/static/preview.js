const proposta = JSON.parse(sessionStorage.getItem('proposta') || 'null');

if (!proposta) {
  window.location.href = '/';
}

// ── Recomendação (vale orquestrar?) ──────────────────────────────────────────

if (proposta.recomendacao && proposta.recomendacao.orquestrar === false) {
  const banner = document.createElement('div');
  banner.style.cssText =
    'background:#fef3cd;border:1px solid #e0c97f;color:#664d03;' +
    'padding:12px 16px;border-radius:8px;margin-bottom:1rem;line-height:1.5;';
  banner.textContent = '⚠ ' + proposta.recomendacao.motivo;
  const main = document.querySelector('main.container') || document.body;
  main.insertBefore(banner, main.firstChild);
}

// ── Populate fields ──────────────────────────────────────────────────────────

document.getElementById('claude-md').value = proposta.claude_md ?? '';
document.getElementById('primeiro-prompt').value = proposta.primeiro_prompt ?? '';

renderAgentes(proposta.agentes ?? []);
renderHooks(proposta.hooks ?? []);

// ── Agents ───────────────────────────────────────────────────────────────────

function renderAgentes(agentes) {
  const list = document.getElementById('agentes-list');
  list.innerHTML = '';
  agentes.forEach((ag, i) => list.appendChild(buildAgenteCard(ag, i)));
}

function buildAgenteCard(ag, index) {
  const card = document.createElement('div');
  card.className = 'card';
  card.dataset.index = index;

  const badge = ag.source === 'biblioteca'
    ? '<span class="badge badge-lib">biblioteca</span>'
    : ag.source === 'fixado'
      ? '<span class="badge badge-pin">fixado</span>'
      : '<span class="badge badge-novo">novo</span>';

  card.innerHTML = `
    <div class="card-header">
      <div class="field-inline">
        <label>Nome</label>
        <input type="text" class="agente-name" value="${escHtml(ag.name)}" />
      </div>
      ${badge}
      <button type="button" class="btn-remove" title="Remover agente">×</button>
    </div>
    <div class="field">
      <label>Conteúdo ${ag.source === 'biblioteca' ? '<span class="hint">(deixe vazio para usar template da biblioteca)</span>' : ''}</label>
      <textarea class="code-area agente-conteudo" rows="10" spellcheck="false">${escHtml(ag.conteudo ?? '')}</textarea>
    </div>
  `;

  card.querySelector('.btn-remove').addEventListener('click', () => {
    card.remove();
  });

  return card;
}

document.getElementById('btn-add-agente').addEventListener('click', () => {
  const list = document.getElementById('agentes-list');
  const index = list.children.length;
  list.appendChild(buildAgenteCard({ name: '', source: 'novo', conteudo: '' }, index));
});

// ── Hooks ────────────────────────────────────────────────────────────────────

function renderHooks(hooks) {
  const list = document.getElementById('hooks-list');
  list.innerHTML = '';
  hooks.forEach((h, i) => list.appendChild(buildHookCard(h, i)));
}

function buildHookCard(hook, index) {
  const card = document.createElement('div');
  card.className = 'card';
  card.dataset.index = index;

  const tipoOpts = ['PreToolUse', 'PostToolUse', 'Stop']
    .map(t => `<option value="${t}" ${hook.tipo === t ? 'selected' : ''}>${t}</option>`)
    .join('');

  card.innerHTML = `
    <div class="card-header">
      <div class="field-inline">
        <label>Tipo</label>
        <select class="hook-tipo">${tipoOpts}</select>
      </div>
      <div class="field-inline">
        <label>Matcher</label>
        <input type="text" class="hook-matcher" placeholder="Bash, Write, null..." value="${escHtml(hook.matcher ?? '')}" />
      </div>
      <button type="button" class="btn-remove" title="Remover hook">×</button>
    </div>
    <div class="field">
      <label>Script</label>
      <textarea class="code-area hook-script" rows="6" spellcheck="false">${escHtml(hook.script ?? '')}</textarea>
    </div>
    <div class="field">
      <label>Motivo</label>
      <textarea class="hook-motivo" rows="2" spellcheck="false">${escHtml(hook.motivo ?? '')}</textarea>
    </div>
  `;

  card.querySelector('.btn-remove').addEventListener('click', () => {
    card.remove();
  });

  return card;
}

document.getElementById('btn-add-hook').addEventListener('click', () => {
  const list = document.getElementById('hooks-list');
  const index = list.children.length;
  list.appendChild(buildHookCard({ tipo: 'PreToolUse', matcher: '', script: '', motivo: '' }, index));
});

// ── Collect & navigate ───────────────────────────────────────────────────────

function collect() {
  const agentes = Array.from(document.querySelectorAll('#agentes-list .card')).map(card => ({
    name: card.querySelector('.agente-name').value.trim(),
    source: card.querySelector('.badge-lib') ? 'biblioteca' : card.querySelector('.badge-pin') ? 'fixado' : 'novo',
    conteudo: card.querySelector('.agente-conteudo').value.trim() || null,
  }));

  const hooks = Array.from(document.querySelectorAll('#hooks-list .card')).map(card => ({
    tipo: card.querySelector('.hook-tipo').value,
    matcher: card.querySelector('.hook-matcher').value.trim() || null,
    script: card.querySelector('.hook-script').value.trim(),
    motivo: card.querySelector('.hook-motivo').value.trim(),
  }));

  return {
    pasta: proposta.pasta,
    claude_md: document.getElementById('claude-md').value,
    agentes,
    hooks,
    primeiro_prompt: document.getElementById('primeiro-prompt').value,
    plano: proposta.plano ?? [],
    // Gate: projeto grande delegável → launch.sh sobe em opus (opus delega; sonnet faz inline).
    orquestrar: proposta.recomendacao?.orquestrar === true,
  };
}

document.getElementById('btn-voltar').addEventListener('click', () => {
  window.location.href = '/';
});

// ── Generate ─────────────────────────────────────────────────────────────────

async function postGenerate(payload) {
  const res = await fetch('/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (res.status === 409) {
    const body = await res.json().catch(() => null);
    return { conflitos: body?.detail?.conflitos ?? [] };
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }

  return { result: await res.json() };
}

document.getElementById('btn-gerar').addEventListener('click', async () => {
  const payload = { ...collect(), sobrescrever: false };
  sessionStorage.setItem('proposta', JSON.stringify({ ...proposta, ...payload }));

  const btn = document.getElementById('btn-gerar');
  const status = document.getElementById('status');
  btn.disabled = true;
  status.textContent = 'Gerando projeto...';
  status.className = 'status loading';

  try {
    let { conflitos, result } = await postGenerate(payload);

    if (conflitos) {
      const lista = conflitos.map(arq => `- ${arq}`).join('\n');
      const confirmar = confirm(
        `Os seguintes arquivos já existem na pasta de destino e serão sobrescritos:\n\n${lista}\n\nDeseja continuar?`
      );

      if (!confirmar) {
        status.textContent = 'Geração cancelada — escolha outra pasta ou confirme a sobrescrita.';
        status.className = 'status';
        btn.disabled = false;
        return;
      }

      ({ result } = await postGenerate({ ...payload, sobrescrever: true }));
    }

    sessionStorage.setItem('gerado', JSON.stringify(result));
    window.location.href = '/generating';
  } catch (err) {
    status.textContent = `Erro: ${err.message}`;
    status.className = 'status error';
    btn.disabled = false;
  }
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
