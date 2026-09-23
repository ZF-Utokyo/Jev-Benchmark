(() => {
  'use strict';
  const menu = document.querySelector('.menu-toggle');
  const nav = document.getElementById('main-nav');
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open));
    nav.classList.toggle('is-open', open);
  });
  nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    nav.classList.remove('is-open'); menu.setAttribute('aria-expanded', 'false');
  }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && nav.classList.contains('is-open')) {
      nav.classList.remove('is-open'); menu.setAttribute('aria-expanded', 'false'); menu.focus();
    }
  });
  const copyButton = document.getElementById('copy-command');
  copyButton.addEventListener('click', async () => {
    const command = document.getElementById('reproduce-command').textContent;
    try {
      await navigator.clipboard.writeText(command);
      copyButton.textContent = 'Copied';
      document.getElementById('copy-status').textContent = 'Reproduction commands copied.';
      setTimeout(() => { copyButton.textContent = 'Copy commands'; }, 2200);
    } catch (_) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(document.getElementById('reproduce-command'));
      selection.removeAllRanges(); selection.addRange(range);
      copyButton.textContent = 'Select & copy';
      document.getElementById('copy-status').textContent = 'Commands selected. Use your keyboard copy command.';
    }
  });

  const data = window.JEV_RESULTS;
  if (!Array.isArray(data)) return;
  const svg = document.getElementById('tradeoff-chart');
  const ns = 'http://www.w3.org/2000/svg';
  let axis = 'cost', filter = 'all', selected = 'jev';
  const colors = {jev: '#2357d9', hosted: '#45776e', local: '#a97929'};
  const positions = {
    cost: {jev:[12,1], 'gemini-flash-lite':[12,-13], luna:[12,19], 'gemini-pro':[-12,-18], astra:[-12,15], qwen4b:[-12,21], qwen9b:[-12,20], 'claude-sonnet5':[12,8], terra:[12,-15], 'claude-haiku45':[12,20]},
    time: {jev:[12,19], 'gemini-flash-lite':[12,-10], luna:[12,18], 'gemini-pro':[12,-14], astra:[12,16], qwen4b:[-12,20], qwen9b:[-12,20], 'claude-sonnet5':[-12,17], terra:[12,-14], 'claude-haiku45':[12,20]}
  };
  function node(tag, attrs, text) {
    const el = document.createElementNS(ns, tag);
    Object.entries(attrs || {}).forEach(([k,v]) => el.setAttribute(k,String(v)));
    if (text !== undefined) el.textContent = text;
    svg.appendChild(el); return el;
  }
  function detail(model) {
    selected = model.key;
    const box = document.getElementById('model-detail');
    box.replaceChildren();
    [model.name, `${model.accuracy.toFixed(2)}% accuracy`, `$${model.cost.toFixed(6)} / contract`, `${model.time.toFixed(2)} s median`, `${model.all12} / 30 all twelve correct`].forEach((value, i) => {
      const el = document.createElement(i ? 'span' : 'strong'); el.textContent = value;
      if (i === 0) {
        const icon = document.querySelector(`tr[data-model="${model.key}"] .model-icon`);
        if (icon) el.prepend(icon.cloneNode(true));
      }
      box.appendChild(el);
    });
    document.querySelectorAll('tbody tr').forEach(row => row.classList.toggle('highlighted', row.dataset.model === model.key));
    svg.querySelectorAll('[data-key] .selection-ring').forEach(el => el.setAttribute('opacity',el.parentNode.dataset.key === selected ? '.24' : '0'));
  }
  function draw() {
    svg.replaceChildren();
    const isCost = axis === 'cost';
    document.getElementById('chart-heading').textContent = isCost ? 'Accuracy and the cost of a decision' : 'Accuracy and the time to a decision';
    node('title', {id:'chart-title'}, `Baseline accuracy versus ${isCost ? 'inference cost' : 'median response time'}`);
    node('desc', {id:'chart-desc'}, 'Ten evaluated configurations. Baseline accuracy uses 123 contracts and 2,091 judgments per model. The horizontal axis is logarithmic. Exact data is available in the table below.');
    const left = 65, right = 944, top = 46, bottom = 359;
    const lo = isCost ? Math.log10(.00018) : Math.log10(.85);
    const hi = isCost ? Math.log10(.18) : Math.log10(260);
    const x = v => left + (Math.log10(v)-lo)/(hi-lo)*(right-left);
    const y = v => bottom - (v-72)/14*(bottom-top);
    const ticks = isCost ? [.0002,.001,.005,.02,.1] : [1,2,5,10,30,100,200];
    for (let value = 72; value <= 86; value += 2) {
      node('line',{x1:left,y1:y(value),x2:right,y2:y(value),stroke:'#e8edf4','stroke-width':1});
      node('text',{x:left-14,y:y(value)+4,'text-anchor':'end',fill:'#778292','font-size':11},`${value}%`);
    }
    ticks.forEach(value => {
      node('line',{x1:x(value),y1:bottom,x2:x(value),y2:bottom+5,stroke:'#b8c2cf'});
      node('text',{x:x(value),y:bottom+22,'text-anchor':'middle',fill:'#778292','font-size':11},isCost ? `$${value}` : `${value} s`);
    });
    node('text',{x:left,y:22,fill:'#65707f','font-size':11},'Baseline accuracy ↑');
    node('text',{x:(left+right)/2,y:bottom+57,'text-anchor':'middle',fill:'#65707f','font-size':11},isCost ? 'Mean inference cost per baseline contract (USD, log scale) →' : 'Median client elapsed time per baseline contract (seconds, log scale) →');
    const shown = data.filter(d => filter === 'all' || d.kind === 'jev' || d.kind === filter);
    shown.forEach(model => {
      const px = x(model[axis]), py = y(model.accuracy), color = colors[model.kind];
      const g = node('g',{class:'chart-point',tabindex:0,role:'button','data-key':model.key,'aria-label':`${model.name}: ${model.accuracy.toFixed(2)} percent accuracy, ${model.cost.toFixed(6)} dollars per contract, ${model.time.toFixed(2)} seconds median. Select for details.`});
      function add(tag, attrs) { const el = document.createElementNS(ns,tag); Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v)); g.appendChild(el); return el; }
      add('circle',{class:'selection-ring',cx:px,cy:py,r:13,fill:color,opacity:selected===model.key?'.24':'0'});
      add('circle',{class:'focus-ring',cx:px,cy:py,r:12,fill:'none',stroke:color,'stroke-width':2,opacity:'0'});
      add('circle',{cx:px,cy:py,r:model.key==='jev'?6:5,fill:color,stroke:'#fff','stroke-width':1.5});
      const [dx,dy]=positions[axis][model.key];
      const label=add('text',{x:px+dx,y:py+dy,'text-anchor':dx<0?'end':'start',fill:color,'font-size':11,'font-weight':model.key==='jev'?700:500,'dominant-baseline':'middle'}); label.textContent=model.short;
      const icon = document.querySelector(`tr[data-model="${model.key}"] .model-icon`);
      if (icon) {
        const size = 14, gap = 4;
        const iconX = dx < 0 ? px + dx - label.getComputedTextLength() - size - gap : px + dx;
        if (dx >= 0) label.setAttribute('x', px + dx + size + gap);
        add('image', {class:'chart-model-icon',href:icon.getAttribute('src'),x:iconX,y:py+dy-size/2,width:size,height:size,preserveAspectRatio:'xMidYMid meet','aria-hidden':'true'});
      }
      g.addEventListener('click',()=>detail(model));
      g.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();detail(model);}});
    });
    document.getElementById('chart-subtitle').textContent = `123 contracts · 2,091 judgments per model · ${shown.length} configurations shown`;
  }
  document.querySelectorAll('[data-axis]').forEach(button => button.addEventListener('click', () => {
    axis = button.dataset.axis;
    document.querySelectorAll('[data-axis]').forEach(b=>b.setAttribute('aria-pressed', String(b===button)));
    draw();
  }));
  document.getElementById('model-filter').addEventListener('change',event=>{filter=event.target.value;if(!data.some(d=>d.key===selected&&(filter==='all'||d.kind==='jev'||d.kind===filter)))detail(data.find(d=>d.key==='jev'));draw();});
  draw();
})();
