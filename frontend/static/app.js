const form = document.getElementById('form-analyze');
const btn = document.getElementById('btn-analisar');
const status = document.getElementById('status');

let globalAgents = [];

// ── Folder picker ─────────────────────────────────────────────────────────────

document.getElementById('btn-browse').addEventListener('click', async () => {
  const btnBrowse = document.getElementById('btn-browse');
  btnBrowse.disabled = true;
  btnBrowse.textContent = '...';
  try {
    const res = await fetch(`/pick-folder?t=${Date.now()}`);
    const data = await res.json();
    if (data.path) {
      document.getElementById('pasta').value = data.path;
    }
  } catch (_) {
    // silently ignore — user can type manually
  } finally {
    btnBrowse.disabled = false;
    btnBrowse.textContent = 'Escolher';
  }
});

// ── Agents library ────────────────────────────────────────────────────────────

async function loadAgents() {
  try {
    const res = await fetch('/agents');
    if (!res.ok) return;
    globalAgents = await res.json();

    const grid = document.getElementById('agents-grid');
    if (!globalAgents.length) {
      grid.innerHTML = '<p class="hint">Nenhum agente disponível ainda.</p>';
      return;
    }

    grid.innerHTML = '';
    globalAgents.forEach(agent => {
      const label = document.createElement('label');
      label.className = `agent-card${agent.pinned ? ' is-pinned' : ''}`;
      label.htmlFor = `agchk-${agent.name}`;
      label.innerHTML = `
        <input type="checkbox" id="agchk-${escHtml(agent.name)}" class="agent-pin-chk"
               data-name="${escHtml(agent.name)}" ${agent.pinned ? 'checked' : ''}>
        <div class="agent-info">
          <span class="agent-name">${escHtml(agent.name)}</span>
          <span class="agent-desc">${escHtml(agent.description || '')}</span>
        </div>
        <span class="badge ${agent.source === 'global' ? 'badge-novo' : 'badge-lib'}">${escHtml(agent.source)}</span>
      `;
      label.querySelector('.agent-pin-chk').addEventListener('change', async (e) => {
        const name = e.target.dataset.name;
        const pinned = e.target.checked;
        label.classList.toggle('is-pinned', pinned);
        const ag = globalAgents.find(a => a.name === name);
        if (ag) ag.pinned = pinned;
        await fetch(`/agents/${encodeURIComponent(name)}/pin`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pinned }),
        });
      });
      grid.appendChild(label);
    });
  } catch (_) {
    const grid = document.getElementById('agents-grid');
    grid.innerHTML = '<p class="hint">Erro ao carregar agentes.</p>';
  }
}

loadAgents();

// ── Project history ───────────────────────────────────────────────────────────

async function loadProjects() {
  try {
    const res = await fetch('/projects');
    if (!res.ok) return;
    const projects = await res.json();
    if (!projects.length) return;

    const section = document.getElementById('section-history');
    const list = document.getElementById('projects-list');
    section.classList.remove('hidden');

    projects.slice().reverse().forEach(p => {
      const li = document.createElement('li');
      li.className = 'project-item';
      const date = new Date(p.criado_em).toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
      li.innerHTML = `
        <span class="project-path">${escHtml(p.pasta)}</span>
        <span class="project-meta">${p.files.length} arquivo${p.files.length !== 1 ? 's' : ''} · ${date}</span>
        <button type="button" class="btn-usage">ver consumo do build</button>
        <span class="usage-result hint"></span>
      `;
      const btnUsage = li.querySelector('.btn-usage');
      const out = li.querySelector('.usage-result');
      btnUsage.addEventListener('click', () => loadUsage(p.pasta, btnUsage, out));
      list.appendChild(li);
    });
  } catch (_) {
    // silently ignore — history is non-critical
  }
}

async function loadUsage(pasta, btn, out) {
  btn.disabled = true;
  out.textContent = 'lendo transcript do build...';
  try {
    const res = await fetch(`/usage?pasta=${encodeURIComponent(pasta)}`);
    const u = await res.json();
    if (!u.encontrado) {
      out.textContent = 'sem sessão de build registrada ainda — abra o Claude Code no projeto.';
    } else {
      const novo = u.input_fresco + u.cache_creation + u.output;
      const custo = u.custo_usd ? ` · <strong>~$${u.custo_usd}</strong>` : '';
      const modelos = (u.modelos && u.modelos.length)
        ? ` <span class="hint">(${u.modelos.join(', ')})</span>` : '';
      out.innerHTML =
        `<strong>${fmt(u.total)}</strong> tokens no build${custo}${modelos} · ` +
        `novo (gerado): <strong>${fmt(novo)}</strong> · ` +
        `releitura de contexto: ${fmt(u.cache_read)} <span class="hint">(~10× mais barata)</span> · ` +
        `${u.mensagens} mensagens`;
    }
  } catch (_) {
    out.textContent = 'erro ao ler o consumo.';
  } finally {
    btn.disabled = false;
  }
}

function fmt(n) {
  return Number(n).toLocaleString('pt-BR');
}

loadProjects();

function showStatus(msg, type) {
  status.textContent = msg;
  status.className = `status ${type}`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const descricao = document.getElementById('descricao').value.trim();
  const pasta = document.getElementById('pasta').value.trim();

  btn.disabled = true;
  showStatus('Analisando projeto...', 'loading');

  try {
    const res = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ descricao, pasta }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? res.statusText);
    }

    const data = await res.json();

    // Merge pinned agents (take priority, dedupe by name)
    const pinned = globalAgents.filter(a => a.pinned);
    const pinnedNames = new Set(pinned.map(a => a.name));
    const aiUnique = (data.agentes ?? []).filter(a => !pinnedNames.has(a.name));
    const mergedAgentes = [
      ...pinned.map(a => ({ name: a.name, source: 'fixado', conteudo: a.conteudo })),
      ...aiUnique,
    ];

    sessionStorage.setItem('proposta', JSON.stringify({ ...data, pasta, agentes: mergedAgentes }));
    window.location.href = '/preview';
  } catch (err) {
    showStatus(`Erro: ${err.message}`, 'error');
    btn.disabled = false;
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
