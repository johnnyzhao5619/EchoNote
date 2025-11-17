const state = {
  bindings: {
    heroEyebrow: document.querySelector('[data-content="hero-eyebrow"]'),
    heroTitle: document.querySelector('[data-content="hero-title"]'),
    heroDescription: document.querySelector('[data-content="hero-description"]'),
    ctaTitle: document.querySelector('[data-content="cta-title"]'),
    ctaDescription: document.querySelector('[data-content="cta-description"]'),
    versionBadges: document.querySelectorAll('[data-version-target]'),
  },
  nodes: {
    heroActions: document.getElementById('heroActions'),
    heroMeta: document.getElementById('heroMeta'),
    statsGrid: document.getElementById('statsGrid'),
    useCaseGrid: document.getElementById('useCaseGrid'),
    featureGrid: document.getElementById('featureGrid'),
    workflowTimeline: document.getElementById('workflowTimeline'),
    integrationGrid: document.getElementById('integrationGrid'),
    ctaActions: document.getElementById('ctaActions'),
    footerVersion: document.getElementById('footerVersion'),
    message: document.getElementById('appMessage'),
  },
};

async function bootstrap() {
  try {
    const response = await fetch('site-content.json', { cache: 'no-cache' });
    if (!response.ok) {
      throw new Error(`无法加载内容（${response.status}）`);
    }
    const content = await response.json();
    applyMeta(content.meta);
    renderHero(content.hero);
    renderStats(content.stats);
    renderUseCases(content.useCases);
    renderFeatures(content.featureGroups);
    renderWorkflow(content.workflow);
    renderIntegrations(content.integrations);
    renderCTA(content.cta);
    setStatus('页面已就绪');
  } catch (error) {
    console.error(error);
    setStatus('加载页面内容失败，请刷新或检查文件路径。');
  }
}

function applyMeta(meta = {}) {
  if (meta.title) {
    document.title = meta.title;
  }
  if (meta.description) {
    const descTag = document.querySelector('meta[name="description"]');
    if (descTag) {
      descTag.setAttribute('content', meta.description);
    }
  }
  if (meta.version) {
    state.bindings.versionBadges.forEach((node) => {
      node.textContent = meta.version;
    });
    if (state.nodes.footerVersion) {
      state.nodes.footerVersion.textContent = meta.version;
    }
  }
}

function renderHero(hero = {}) {
  const { eyebrow, title, description, actions = [], meta = [] } = hero;
  if (state.bindings.heroEyebrow) {
    state.bindings.heroEyebrow.textContent = eyebrow ?? '';
  }
  if (state.bindings.heroTitle) {
    state.bindings.heroTitle.textContent = title ?? '';
  }
  if (state.bindings.heroDescription) {
    state.bindings.heroDescription.textContent = description ?? '';
  }
  replaceChildren(state.nodes.heroActions, actions.map(createButton));
  if (state.nodes.heroMeta) {
    replaceChildren(
      state.nodes.heroMeta,
      meta.map((item) => {
        const span = document.createElement('span');
        span.textContent = item;
        return span;
      }),
    );
  }
}

function renderStats(stats = []) {
  replaceChildren(
    state.nodes.statsGrid,
    stats.map((stat) => {
      const card = document.createElement('article');
      card.className = 'stat-card';
      const value = document.createElement('strong');
      value.textContent = stat.value;
      const label = document.createElement('p');
      label.textContent = stat.label;
      const detail = document.createElement('span');
      detail.textContent = stat.detail ?? '';
      detail.className = 'card__body';
      card.append(value, label, detail);
      return card;
    }),
  );
}

function renderUseCases(useCases = []) {
  replaceChildren(
    state.nodes.useCaseGrid,
    useCases.map((useCase) => {
      const card = document.createElement('article');
      card.className = 'card';
      const title = document.createElement('h3');
      title.className = 'card__title';
      title.textContent = useCase.title;
      const body = document.createElement('p');
      body.className = 'card__body';
      body.textContent = useCase.description;
      const highlights = document.createElement('ul');
      highlights.className = 'panel__list';
      useCase.highlights?.forEach((point) => {
        const li = document.createElement('li');
        li.textContent = point;
        highlights.appendChild(li);
      });
      card.append(title, body, highlights);
      return card;
    }),
  );
}

function renderFeatures(featureGroups = []) {
  replaceChildren(
    state.nodes.featureGrid,
    featureGroups.map((group) => {
      const card = document.createElement('article');
      card.className = 'feature-card';
      const heading = document.createElement('h3');
      heading.textContent = group.title;
      const info = document.createElement('p');
      info.textContent = group.description;
      const list = document.createElement('ul');
      group.items?.forEach((item) => {
        const li = document.createElement('li');
        li.textContent = `${item.title}：${item.detail}`;
        list.appendChild(li);
      });
      card.append(heading, info, list);
      return card;
    }),
  );
}

function renderWorkflow(workflow = { steps: [] }) {
  const { steps = [] } = workflow;
  replaceChildren(
    state.nodes.workflowTimeline,
    steps.map((step, index) => {
      const container = document.createElement('article');
      container.className = 'workflow-step';
      container.dataset.step = index + 1;
      const title = document.createElement('h3');
      title.textContent = step.title;
      const copy = document.createElement('p');
      copy.textContent = step.description;
      container.append(title, copy);
      return container;
    }),
  );
}

function renderIntegrations(integrations = []) {
  replaceChildren(
    state.nodes.integrationGrid,
    integrations.map((integration) => {
      const card = document.createElement('article');
      card.className = 'integration-card';
      const name = document.createElement('strong');
      name.textContent = integration.name;
      const desc = document.createElement('p');
      desc.className = 'card__body';
      desc.textContent = integration.description;
      const status = document.createElement('span');
      status.textContent = integration.status;
      status.className = 'hero__eyebrow';
      card.append(name, desc, status);
      return card;
    }),
  );
}

function renderCTA(cta = {}) {
  if (state.bindings.ctaTitle) {
    state.bindings.ctaTitle.textContent = cta.title ?? '';
  }
  if (state.bindings.ctaDescription) {
    state.bindings.ctaDescription.textContent = cta.description ?? '';
  }
  replaceChildren(state.nodes.ctaActions, (cta.actions ?? []).map(createButton));
}

function createButton(action = {}) {
  const anchor = document.createElement('a');
  anchor.className = `button button--${action.variant ?? 'primary'}`;
  anchor.href = action.href;
  anchor.target = action.external === false ? '_self' : '_blank';
  anchor.rel = 'noreferrer';
  anchor.textContent = action.label;
  return anchor;
}

function replaceChildren(node, children = []) {
  if (!node) return;
  node.innerHTML = '';
  children.forEach((child) => node.appendChild(child));
}

function setStatus(message) {
  if (state.nodes.message) {
    state.nodes.message.textContent = message;
  }
}

document.addEventListener('DOMContentLoaded', bootstrap);
