/* app.js -- BiteRec front-end controller */
const App = (() => {
  const state = {
    user: null, profile: null,
    weight: 0.7,
    showHealth: true, showEco: true,
    results: [],
    current: null,
    allergens: new Set(),
    allergensAvailable: [],
    favorites: new Set(),
    history: load('biterec_history', []),
    acSel: -1,
    overviewLoaded: false,
    shapGrades: null,        // last-rendered per-grade SHAP payload (for selector)
    shapGradeTarget: 'rec',  // which container the selector writes to
  };

  /* ---------------------------------------------------------- utilities */
  function load(k, d){ try{ return JSON.parse(localStorage.getItem(k)) ?? d; }catch{ return d; } }
  function save(k, v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch{} }
  const $ = s => document.querySelector(s);
  const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  function api(url, opts){ return fetch(url, opts).then(r => r.json()); }
  let toastT;
  function toast(msg){ const t=$('#toast'); t.textContent=msg; t.hidden=false; clearTimeout(toastT); toastT=setTimeout(()=>t.hidden=true,2400); }
  const debounce=(fn,ms)=>{let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),ms);};};

  function badge(kind, grade){
    const g=(grade||'').toLowerCase();
    const lbl=kind==='nutri'?'Nutri':'Eco';
    return `<span class="badge g-${g}" title="${lbl}-Score ${g.toUpperCase()}"><span class="lbl">${lbl}</span> ${g.toUpperCase()}</span>`;
  }
  const PH_HTML = "<div class='ph'>&#127869;</div>";
  function imgFallback(el){ if(el && el.parentNode) el.parentNode.innerHTML = PH_HTML; }
  function img(p){
    return p && p.image
      ? `<img loading="lazy" src="${esc(p.image)}" alt="${esc(p.name)}" onerror="App.imgFallback(this)">`
      : PH_HTML;
  }
  function combined(p){ return Math.round((state.weight*p.health_score + (1-state.weight)*p.eco_score)*10)/10; }

  /* ---------------------------------------------------------- navigation + gate */
  function gated(){ return !state.user; }
  function needsOnboarding(){ return !!state.user && state.profile && state.profile.onboarded===false; }
  function go(view){
    if(gated() && view !== 'account'){ toast('Please create an account or sign in to use BiteRec'); view='account'; }
    else if(needsOnboarding() && view !== 'account'){ toast('Set your preferences first, then start searching'); view='account'; }
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
    $('#view-'+view).classList.add('active');
    document.querySelectorAll('.nav-link').forEach(n=>n.classList.toggle('active', n.dataset.view===view));
    $('#nav').classList.remove('open');
    window.scrollTo({top:0,behavior:'smooth'});
    if(view==='insights') loadOverview();
    if(view==='favorites') loadFavorites();
    if(view==='account') renderAccount();
  }
  function toggleNav(){ $('#nav').classList.toggle('open'); }
  function applyGateUI(){ document.body.classList.toggle('signed-out', gated()); }

  /* ---------------------------------------------------------- autocomplete + history */
  const acBox = () => $('#autocomplete');
  function historyDropdown(){
    if(!state.history.length) return hideAC();
    const items = state.history.slice(0,6).map(h=>{
      const safe=esc(h).replace(/'/g,"\\'");
      return `<div class="ac-item ac-hist">
        <span class="ac-hist-main" onclick="App.pickHistory('${safe}')">
          <svg class="ac-clock" viewBox="0 0 24 24"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 5h-2v6l5 3 1-1.7-4-2.3V7z"/></svg>
          <span class="ac-name">${esc(h)}</span>
        </span>
        <button class="ac-remove" title="Remove from recent searches" onmousedown="event.preventDefault()" onclick="App.removeHistory('${safe}',event)">&times;</button>
      </div>`;
    }).join('');
    acBox().innerHTML = `<div class="ac-head">Recent searches</div><div class="ac-history">${items}</div>`;
    acBox().hidden=false; state.acSel=-1;
  }
  function removeHistory(q, ev){
    if(ev){ ev.stopPropagation(); ev.preventDefault(); }
    state.history = state.history.filter(h=>h.toLowerCase()!==(q||'').toLowerCase());
    save('biterec_history', state.history);
    if(state.history.length){ historyDropdown(); } else { hideAC(); }
  }
  const suggest = debounce(q=>{
    if(!q){ historyDropdown(); return; }
    api('/api/suggest?q='+encodeURIComponent(q)).then(list=>{
      if(!list.length){ hideAC(); return; }
      acBox().innerHTML = list.map(s=>`
        <div class="ac-item" onclick="App.openFromSuggest(${s.id}, '${esc(s.name).replace(/'/g,"\\'")}')">
          <div class="ac-thumb">${s.image?`<img loading="lazy" src="${esc(s.image)}" onerror="this.style.display='none'">`:''}</div>
          <div class="ac-meta"><div class="ac-name">${esc(s.name)}</div><div class="ac-brand">${esc(s.brand||s.category)}</div></div>
          <div class="ac-grades">${badge('nutri',s.nutriscore)}${badge('eco',s.ecoscore)}</div>
        </div>`).join('');
      acBox().hidden=false; state.acSel=-1;
    });
  },160);
  function hideAC(){ acBox().hidden=true; state.acSel=-1; }
  function onSearchKey(e){
    const items=[...acBox().querySelectorAll('.ac-item')];
    if(e.key==='ArrowDown'&&items.length){ e.preventDefault(); state.acSel=(state.acSel+1)%items.length; }
    else if(e.key==='ArrowUp'&&items.length){ e.preventDefault(); state.acSel=(state.acSel-1+items.length)%items.length; }
    else if(e.key==='Enter'){ if(state.acSel>=0&&items[state.acSel]){ items[state.acSel].click(); } else runSearch($('#search-input').value); return; }
    else if(e.key==='Escape'){ hideAC(); return; }
    items.forEach((it,i)=>it.classList.toggle('active', i===state.acSel));
  }
  function pickHistory(q){ $('#search-input').value=q; hideAC(); runSearch(q); }
  function openFromSuggest(id,name){ addHistory(name); hideAC(); $('#search-input').value=name; openProduct(id); }
  function addHistory(q){
    q=(q||'').trim(); if(!q) return;
    state.history = [q, ...state.history.filter(h=>h.toLowerCase()!==q.toLowerCase())].slice(0,10);
    save('biterec_history', state.history);
  }

  /* ---------------------------------------------------------- search + results */
  function runSearch(q){
    q=(q||'').trim(); if(!q){ return; }
    addHistory(q); hideAC(); $('#rec-panel').hidden=true; state.current=null;
    api('/api/search?q='+encodeURIComponent(q)).then(list=>{ state.results=list; renderResults(); });
  }
  function resultCard(p){
    const fav = state.favorites.has(p.id);
    return `<div class="card">
        <div class="card-img" onclick="App.openProduct(${p.id})">${img(p)}</div>
        <div class="card-body">
          <div class="card-name" onclick="App.openProduct(${p.id})">${esc(p.name)}</div>
          ${p.brand?`<div class="card-brand">${esc(p.brand)}</div>`:''}
          ${p.category&&p.category!=='unknown'?`<div class="card-cat">${esc(p.category)}</div>`:''}
          <div class="card-grades">${badge('nutri',p.nutriscore)}${badge('eco',p.ecoscore)}</div>
          <div class="card-actions">
            <button class="mini-btn" onclick="App.openDetail(${p.id})">Details</button>
            <button class="mini-btn primary" onclick="App.openProduct(${p.id})">Alternatives</button>
            <button class="icon-fav ${fav?'on':''}" title="Save" onclick="App.toggleFav(${p.id},event)">${fav?'&#10084;':'&#9825;'}</button>
          </div>
        </div>
      </div>`;
  }
  function renderResults(){
    const grid=$('#results'), empty=$('#results-empty');
    const list = state.results.filter(passesFiltersClient).sort((a,b)=>combined(b)-combined(a));
    if(!state.results.length){ grid.innerHTML=''; empty.hidden=false; empty.innerHTML='<strong>Start by searching a product</strong>Type a name above to see healthier and greener alternatives.'; return; }
    if(!list.length){ grid.innerHTML=''; empty.hidden=false; empty.innerHTML='<strong>No matches with these filters</strong>Try relaxing a filter, or change your saved allergens in Account.'; return; }
    empty.hidden=true; grid.innerHTML = list.map(resultCard).join('');
  }

  /* ---------------------------------------------------------- recommendation view */
  function openProduct(id){
    if(gated()) return go('account');
    if(!$('#view-discover').classList.contains('active')) go('discover');  // works from Favourites too
    state.current=id; refreshRecommendation(); window.scrollTo({top:0,behavior:'smooth'});
  }
  function refreshRecommendation(){
    if(state.current==null) return;
    api('/api/recommend/'+state.current+recommendQuery()).then(renderRecommendation);
  }
  // Serialize the active sidebar filters into the recommend query, so changing
  // any filter re-fetches and the recommendation updates instantly.
  function recommendQuery(){
    const f = readFilters();
    const checks = Object.keys(f).filter(k=>f[k]===true);
    const p = new URLSearchParams();
    p.set('w', state.weight);
    p.set('allergens', [...state.allergens].join(','));
    p.set('sh', state.showHealth?1:0);
    p.set('se', state.showEco?1:0);
    if(checks.length) p.set('f', checks.join(','));
    if(f.minNutri) p.set('minNutri', f.minNutri);
    if(f.minEco) p.set('minEco', f.minEco);
    [['max_sugar',f.max_sugar],['min_protein',f.min_protein],['max_salt',f.max_salt],
     ['max_satfat',f.max_satfat],['max_energy',f.max_energy],['min_fibre',f.min_fibre]]
      .forEach(([k,v])=>{ if(v!=null) p.set(k,v); });
    return '?'+p.toString();
  }

  function ecoUnits(p){
    const e=p.eco_metrics;
    return `<div class="eco-units">
      <span>&#127757; <b>~${e.co2_kg} kg</b> CO&#8322;e/kg &middot; like <b>${e.car_km} km</b> by car
        <span class="tip" data-tip="Estimated from the Eco-Score grade and product category. Real per-product carbon data is rarely available in Open Food Facts.">?</span></span>
      <span>&#128167; <b>~${e.water_l} L</b> water/kg</span>
    </div>`;
  }

  function altCard(p){
    const tagClass = p.kind==='Better for You'?'you':'earth';
    const fav = state.favorites.has(p.id);
    const c = p.contrastive||{}; const dh=c.health_delta, de=c.eco_delta;
    const rankBadge = p.rank?`<span class="rank">#${p.rank}</span>`:'';
    return `<div class="rec-card">
      <button class="fav-btn ${fav?'on':''}" title="Save to favourites" onclick="App.toggleFav(${p.id},event)">${fav?'&#10084;':'&#9825;'}</button>
      <div class="rec-tag ${tagClass}">${rankBadge}${esc(p.kind)}</div>
      <div class="thumb" onclick="App.openDetail(${p.id})">${img(p)}</div>
      <div class="rec-name">${esc(p.name)}</div>
      ${p.brand?`<div class="rec-brand">${esc(p.brand)}</div>`:''}
      ${p.category&&p.category!=='unknown'?`<div class="card-cat">${esc(p.category)}</div>`:''}
      <div class="rec-grades">${badge('nutri',p.nutriscore)}${badge('eco',p.ecoscore)}</div>
      <div class="explain">${esc(p.explanation)}</div>
      <div class="contrast">
        ${dh!=null?`<span>Health <span class="${dh>=0?'delta-up':'delta-down'}">${dh>=0?'+':''}${dh}</span></span>`:''}
        ${de!=null?`<span>Eco <span class="${de>=0?'delta-up':'delta-down'}">${de>=0?'+':''}${de}</span></span>`:''}
      </div>
      ${ecoUnits(p)}
      <div class="rec-card-actions">
        <button class="mini-btn" onclick="App.openDetail(${p.id})">Details</button>
        <a class="src-link" href="${esc(p.off_url||'#')}" target="_blank" rel="noopener">Source &#8599;</a>
      </div>
    </div>`;
  }

  /* SHAP waterfall (health OR eco). Plain-language, readable. */
  function shapWaterfall(s, opts){
    opts = opts || {};
    const axisWord = opts.axis==='eco' ? 'environmental' : 'health';
    const gradeLabel = opts.gradeLabel || 'Nutri-Score';
    if(!s || !s.available || !s.features) return `<p class="muted small">A detailed breakdown isn't available for this item.</p>`;
    const maxAbs = Math.max(...s.features.map(f=>Math.abs(f.contribution)), 1);
    const rows = s.features.map(f=>{
      const pos=f.contribution>=0, w=Math.abs(f.contribution)/maxAbs*100;
      const sub = f.unit!=null ? `${f.value} ${f.unit}` : (f.value!=null?`${f.value}`:'');
      return `<div class="wf-row">
        <div class="wf-feat">${esc(f.feature)}${sub?`<span class="wf-val">${esc(String(sub))}</span>`:''}</div>
        <div class="wf-track"><div class="wf-axis"></div><div class="wf-bar ${pos?'pos':'neg'}" style="width:${(w/2).toFixed(1)}%"></div></div>
        <div class="wf-num ${pos?'pos':'neg'}">${pos?'+':''}${f.contribution}</div>
      </div>`;
    }).join('');
    return `<div class="shap">
      <p class="shap-plain">In plain terms: a <b>typical product</b> scores about <b>${s.base}</b> out of 100 on ${axisWord}.
      The factors below add up to move it to <b>${s.predicted}</b> &mdash; this product's score (${gradeLabel} ${s.grade}).</p>
      <div class="shap-summary">
        <span class="shap-chip base">Typical product <b>${s.base}</b></span>
        <span class="shap-arrow">&rarr;</span>
        <span class="shap-chip pred">This product <b>${s.predicted}</b></span>
      </div>
      <p class="shap-lead"><b>How to read it:</b> a bar to the <span class="pos">right</span> means that factor <span class="pos">helped</span> the score; to the <span class="neg">left</span> means it <span class="neg">hurt</span> it. Longer bar = bigger effect.</p>
      <div class="wf">${rows}</div></div>`;
  }

  /* SHAP per-grade probability waterfall (notebook methodology, with grade selector) */
  function shapGradeBlock(sg, target){
    if(!sg || !sg.available) return '<p class="muted small">Detailed SHAP breakdown is unavailable for this item.</p>';
    state.shapGrades = sg; state.shapGradeTarget = target;
    const opts = sg.grades.map(g=>`<option value="${g.grade}" ${g.grade===sg.predicted_grade?'selected':''}>Grade ${g.grade}${g.grade===sg.predicted_grade?' (predicted)':''}</option>`).join('');
    return `<div class="shapg">
      <div class="shapg-ctrl">
        <label>Explain probability of grade:
          <select onchange="App.selectShapGrade(this.value)">${opts}</select>
        </label>
      </div>
      <div class="shapg-body" id="shapg-${target}"></div>
      <p class="muted small"><b>What this shows:</b> the model gives every grade a probability. Pick a grade above to see which nutrients <span class="pos">raise</span> or <span class="neg">lower</span> the chance of <em>that</em> grade for this product. (Method: SHAP, as in <code>off_nutriscore_01.ipynb</code> §5.)</p>
    </div>`;
  }
  function selectShapGrade(grade){
    const sg=state.shapGrades; if(!sg) return;
    const g=sg.grades.find(x=>x.grade===grade)||sg.grades[0];
    const cont=$('#shapg-'+state.shapGradeTarget); if(!cont) return;
    const rows=sg.features.map((feat,i)=>({feat, val:sg.values[i], unit:sg.units[i], v:g.contribs[i]}));
    rows.sort((a,b)=>Math.abs(b.v)-Math.abs(a.v));
    const maxAbs=Math.max(...rows.map(r=>Math.abs(r.v)),0.001);
    const bars=rows.map(r=>{
      const pos=r.v>=0, w=Math.abs(r.v)/maxAbs*100;
      return `<div class="wf-row">
        <div class="wf-feat">${esc(r.feat)}<span class="wf-val">${r.val} ${r.unit}</span></div>
        <div class="wf-track"><div class="wf-axis"></div><div class="wf-bar ${pos?'pos':'neg'}" style="width:${(w/2).toFixed(1)}%"></div></div>
        <div class="wf-num ${pos?'pos':'neg'}">${pos?'+':''}${r.v.toFixed(3)}</div>
      </div>`;
    }).join('');
    cont.innerHTML = `<div class="shapg-summary">
        <span class="shap-chip base">Base P(${g.grade}) <b>${(g.base*100).toFixed(0)}%</b></span>
        <span class="shap-arrow">&rarr;</span>
        <span class="shap-chip pred">This product P(${g.grade}) <b>${(g.fx*100).toFixed(0)}%</b></span>
      </div><div class="wf">${bars}</div>`;
  }

  /* Contrastive comparison table (Original vs alternative) -- like the prototype */
  function contrastTable(base, alt){
    const rows=[
      ['Nutri-Score', base.nutriscore.toUpperCase(), alt.nutriscore.toUpperCase()],
      ['Eco-Score', base.ecoscore.toUpperCase(), alt.ecoscore.toUpperCase()],
      ['Energy (kcal)', base.nutrients.energy_kcal, alt.nutrients.energy_kcal],
      ['Protein (g)', base.nutrients.proteins, alt.nutrients.proteins],
      ['Sugar (g)', base.nutrients.sugars, alt.nutrients.sugars],
      ['Salt (g)', base.nutrients.salt, alt.nutrients.salt],
      ['Fat (g)', base.nutrients.fat, alt.nutrients.fat],
      ['Fibre (g)', base.nutrients.fiber, alt.nutrients.fiber],
      ['CO\u2082 (kg/kg, est.)', base.eco_metrics.co2_kg, alt.eco_metrics.co2_kg],
    ];
    const body=rows.map(r=>`<tr><td>${r[0]}</td><td class="num">${r[1]}</td><td class="num strong">${r[2]}</td></tr>`).join('');
    return `<table class="ct-table"><thead><tr><th>Attribute</th><th>Yours</th><th>${esc(alt.kind)}</th></tr></thead><tbody>${body}</tbody></table>`;
  }

  function noBetterCard(goal){
    const label = goal==='health' ? 'health' : 'the environment';
    const icon = goal==='health' ? '&#129505;' : '&#127757;';
    return `<div class="rec-card no-better">
      <div class="nb-icon">${icon}</div>
      <div class="nb-title">Already a great choice</div>
      <div class="nb-text">We couldn't find a product better for <b>${label}</b> than this one in the same category. Nice pick!</div>
    </div>`;
  }
  function renderRecommendation(r){
    if(r.error){ toast('Product not found'); return; }
    const base=r.base;
    const panel=$('#rec-panel'); panel.hidden=false; $('#results').innerHTML=''; $('#results-empty').hidden=true;
    const baseFav = state.favorites.has(base.id);
    const alts = r.alternatives||[];
    const unavailable = r.unavailable||[];
    const modeNote = r.mode==='health' ? 'Showing your top healthier alternatives.'
                   : r.mode==='eco' ? 'Showing your top greener alternatives.'
                   : 'One healthier and one greener alternative.';

    // Build the alternative slots, inserting a clear "no better option" card
    // for any goal the engine couldn't improve on (note a).
    let altCards = alts.map(altCard).join('');
    unavailable.forEach(g=>{ altCards += noBetterCard(g); });
    if(!alts.length && !unavailable.length)
      altCards = '<div class="rec-card empty-alt">No allergen-safe alternative in <b>'+esc(base.category)+'</b> matches your current filters. Try relaxing a filter or allergen.</div>';

    panel.innerHTML = `
      <button class="rec-back" onclick="App.backToResults()">&larr; Back to results</button>
      <p class="rec-mode-note">${modeNote} <a href="#" onclick="App.go('account');return false">Change in Account</a></p>
      <div class="rec-cards">
        <div class="rec-card is-base">
          <button class="fav-btn ${baseFav?'on':''}" onclick="App.toggleFav(${base.id},event)" title="Save">${baseFav?'&#10084;':'&#9825;'}</button>
          <div class="rec-tag">You searched</div>
          <div class="thumb" onclick="App.openDetail(${base.id})">${img(base)}</div>
          <div class="rec-name">${esc(base.name)}</div>
          ${base.brand?`<div class="rec-brand">${esc(base.brand)}</div>`:''}
          ${base.category&&base.category!=='unknown'?`<div class="card-cat">${esc(base.category)}</div>`:''}
          <div class="rec-grades">${badge('nutri',base.nutriscore)}${badge('eco',base.ecoscore)}</div>
          ${ecoUnits(base)}
          <div class="rec-card-actions">
            <button class="mini-btn" onclick="App.openDetail(${base.id})">Details</button>
            <a class="src-link" href="${esc(base.off_url||'#')}" target="_blank" rel="noopener">Source &#8599;</a>
          </div>
        </div>
        ${altCards}
      </div>

      ${alts.length?`<div class="rec-chart-card wide">
        <h3>Side-by-side comparison <span class="tip" data-tip="Open any product's Details to see the full SHAP explanation of its grades.">?</span></h3>
        <div class="ct-grid">${alts.map(a=>`<div class="ct-block"><h4>${esc(a.kind)}${a.rank?` #${a.rank}`:''}</h4>${contrastTable(base,a)}</div>`).join('')}</div>
        <p class="muted small">Want to know <em>why</em> a product gets its grades? Tap <b>Details</b> on any card.</p>
      </div>`:''}`;
  }
  function backToResults(){ $('#rec-panel').hidden=true; state.current=null; renderResults(); }

  /* ---------------------------------------------------------- product detail modal */
  function openDetail(id){ if(gated()) return go('account'); api('/api/detail/'+id).then(d=>{ if(d.error){ toast('Product not found'); return; } renderDetail(d); }); }
  function closeDetail(){ $('#detail-modal').hidden=true; document.body.classList.remove('modal-open'); Charts.destroy('d-nutri'); Charts.destroy('d-eco'); }
  function zoomChart(which){
    const r=state.detailRadars; if(!r) return;
    const data = which==='nutri'?r.nutri:r.eco;
    const color = which==='nutri'?'#4f9d6e':'#3a7355';
    $('#zoom-title').textContent = (which==='nutri'?'Nutrition profile':'Ecology profile')+' — '+(r.name||'');
    $('#chart-zoom').hidden=false;
    setTimeout(()=>Charts.radar('zoom-canvas', Object.keys(data), [{label:which==='nutri'?'Nutrition':'Ecology', data:Object.values(data), color}]), 30);
  }
  function closeZoom(){ $('#chart-zoom').hidden=true; Charts.destroy('zoom-canvas'); }

  function environmentBlock(d){
    const e=d.eco_metrics; const realScore=d.environmental_score;
    return `<div class="env-block">
      <div class="env-badge g-${(d.ecoscore||'').toLowerCase()}">
        <span class="env-letter">${(d.ecoscore||'?').toUpperCase()}</span>
        <div><b>Eco-Score ${(d.ecoscore||'?').toUpperCase()}</b>${realScore!=null?`<span class="env-num">${realScore}/100 environmental score</span>`:''}</div>
      </div>
      <div class="env-carbon">
        <span class="env-car">&#128663;</span>
        <div><b>Like driving ~${e.car_km} km</b><span class="env-sub">${e.co2_kg} kg CO&#8322;e/kg &middot; ~${e.water_l} L water/kg (estimated)</span></div>
      </div>
      <p class="muted small">Eco-Score is real Open Food Facts data; the carbon/water figures are estimated from the grade and category (per-stage carbon data isn't available in this dataset).</p>
    </div>`;
  }
  function ingredientsBlock(d){
    if(!d.ingredients_text) return '';
    const count = d.ingredients_n ? `<span class="ing-count">&#129348; ${d.ingredients_n} ingredient${d.ingredients_n>1?'s':''}</span>` : '';
    return `<div class="d-block"><h4>Ingredients</h4>${count}<p class="ing-text">${esc(d.ingredients_text)}</p></div>`;
  }
  // OFF-style nutrient traffic lights (UK FSA thresholds, per 100 g)
  function nutritionLevels(d){
    const n=d.nutrients;
    const defs=[
      ['Fat', n.fat, 3, 17.5, 'g'],
      ['Saturated fat', n.saturated_fat, 1.5, 5, 'g'],
      ['Sugars', n.sugars, 5, 22.5, 'g'],
      ['Salt', n.salt, 0.3, 1.5, 'g'],
    ];
    const rows=defs.map(([label,v,lo,hi,u])=>{
      const level = v<=lo?'low':(v<=hi?'moderate':'high');
      const cls = level==='low'?'lvl-low':level==='moderate'?'lvl-mod':'lvl-high';
      return `<div class="nl-row"><span class="nl-dot ${cls}"></span>
        <span class="nl-text"><b>${label}</b> in ${level} quantity</span>
        <span class="nl-val">${v} ${u}</span></div>`;
    }).join('');
    const grades=['A','B','C','D','E'];
    const strip=grades.map(g=>`<span class="ns-cell g-${g.toLowerCase()} ${g===d.nutriscore.toUpperCase()?'on':''}">${g}</span>`).join('');
    return `<div class="health-block">
      <div class="ns-badge"><div class="ns-cap">Nutri-Score</div><div class="ns-strip">${strip}</div></div>
      <div class="nl-list">${rows}</div>
      <p class="muted small">Levels use the UK FSA traffic-light thresholds. Higher fat, saturated fat, sugar and salt are shown amber/red.</p>
    </div>`;
  }
  function ecoShapBlock(d){
    const es=d.eco_shap;
    if(!es || !es.available) return '';
    return `<div class="d-block">
      <h4>Why this Eco-Score? <span class="tip" data-tip="A learned model showing which attributes are associated with the Eco-Score grade in this dataset. The official Eco-Score also uses packaging and transport data not available here.">?</span></h4>
      ${shapWaterfall(es,{axis:'eco',gradeLabel:'Eco-Score'})}
      <p class="muted small">This is a learned approximation: it shows what's <em>associated</em> with the grade in our data (food category matters most). The official Open Food Facts Eco-Score also factors in packaging and transport, which this dataset doesn't include.</p>
    </div>`;
  }
  function renderDetail(d){
    const fav = state.favorites.has(d.id);
    state.detailRadars = {nutri:d.nutrition_radar, eco:d.eco_radar, name:d.name};
    const rows = d.nutrient_table.map(r=>`<tr><td>${esc(r.label)}</td><td class="num">${r.value} ${r.unit}</td></tr>`).join('');
    const allerg = d.allergens.length ? d.allergens.map(a=>`<span class="chip on static">${esc(a)}</span>`).join('') : '<span class="muted">None detected</span>';
    const labels = d.labels ? esc(d.labels).split(',').slice(0,6).map(l=>`<span class="tagpill">${l.trim()}</span>`).join('') : '';
    $('#detail-body').innerHTML = `
      <div class="d-head">
        <div class="d-img">${img(d)}</div>
        <div class="d-head-info">
          <h2>${esc(d.name)}</h2>
          <div class="d-brand">${d.brand?esc(d.brand)+' &middot; ':''}${esc(d.category)}</div>
          <div class="rec-grades">${badge('nutri',d.nutriscore)}${badge('eco',d.ecoscore)}${d.organic?'<span class="tagpill organic">Organic</span>':''}</div>
          <div class="d-actions">
            <button class="icon-fav big ${fav?'on':''}" onclick="App.toggleFav(${d.id},event,true)">${fav?'&#10084; Saved':'&#9825; Save'}</button>
            <button class="mini-btn primary" onclick="App.closeDetail();App.go('discover');App.openProduct(${d.id})">See alternatives</button>
          </div>
        </div>
      </div>

      <div class="d-block">
        <h4>Health &amp; Nutri-Score</h4>
        ${nutritionLevels(d)}
      </div>

      <div class="d-grid">
        <div class="d-block">
          <h4>Nutrition per 100 g</h4>
          <table class="d-table"><tbody>${rows}</tbody></table>
          ${d.additives_n!=null?`<p class="muted small">Additives listed: ${d.additives_n}${d.nova?` &middot; NOVA group ${d.nova}`:''}</p>`:(d.nova?`<p class="muted small">NOVA group ${d.nova}</p>`:'')}
        </div>
        <div class="d-block">
          <h4>Environment <span class="tip" data-tip="Open Food Facts Eco-Score plus an estimated carbon/water footprint.">?</span></h4>
          ${environmentBlock(d)}
        </div>
      </div>
      ${ingredientsBlock(d)}
      <div class="d-block">
        <h4>Allergens (from ingredients)</h4>
        <div class="allergen-chips">${allerg}</div>
        ${labels?`<h4 style="margin-top:.9rem">Labels</h4><div class="tagpills">${labels}</div>`:''}
      </div>
      <div class="d-block">
        <h4>Why this Nutri-Score?</h4>
        ${shapWaterfall(d.shap,{axis:'health',gradeLabel:'Nutri-Score'})}
        <details class="ai-more"><summary>Advanced: per-grade probability breakdown (SHAP)</summary>${shapGradeBlock(d.shap_grades,'det')}</details>
      </div>
      ${ecoShapBlock(d)}
      <div class="d-charts">
        <div class="d-chart"><h4>Nutrition profile <button class="zoom-btn" onclick="App.zoomChart('nutri')" title="Enlarge">&#9974;</button></h4><div class="radar-wrap"><canvas id="d-nutri"></canvas></div></div>
        <div class="d-chart"><h4>Ecology profile <button class="zoom-btn" onclick="App.zoomChart('eco')" title="Enlarge">&#9974;</button></h4><div class="radar-wrap"><canvas id="d-eco"></canvas></div></div>
      </div>
      <a class="src-link block" href="${esc(d.off_url||'#')}" target="_blank" rel="noopener">View full data on Open Food Facts &#8599;</a>`;
    $('#detail-modal').hidden=false; document.body.classList.add('modal-open');
    Charts.radar('d-nutri', Object.keys(d.nutrition_radar), [{label:'Nutrition', data:Object.values(d.nutrition_radar), color:'#4f9d6e'}]);
    Charts.radar('d-eco', Object.keys(d.eco_radar), [{label:'Ecology', data:Object.values(d.eco_radar), color:'#3a7355'}]);
    if(d.shap_grades && d.shap_grades.available) selectShapGrade(d.shap_grades.predicted_grade);
  }

  /* ---------------------------------------------------------- favorites */
  function toggleFav(id, ev, isDetail){
    if(ev) ev.stopPropagation();
    if(!state.user){ toast('Sign in to save favourites'); go('account'); return; }
    api('/api/favorite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:id})})
      .then(r=>{ state.favorites=new Set(r.favorites);
        if(isDetail) openDetail(id);
        if(state.current!=null) refreshRecommendation(); else renderResults();
        if($('#view-favorites').classList.contains('active')) loadFavorites();
        toast(state.favorites.has(id)?'Saved to favourites':'Removed from favourites'); });
  }
  function loadFavorites(){
    const grid=$('#fav-grid'), sub=$('#fav-sub');
    if(!state.user){ grid.innerHTML=''; sub.innerHTML='Sign in to save and revisit products.'; return; }
    api('/api/favorites').then(r=>{
      const list=r.favorites||[];
      sub.textContent = list.length? `${list.length} saved product${list.length>1?'s':''}.` : 'No favourites yet — tap the heart on any product.';
      grid.innerHTML = list.map(resultCard).join('');
    });
  }

  /* ---------------------------------------------------------- filters */
  function readFilters(){
    const f={}; document.querySelectorAll('[data-filter]').forEach(c=>f[c.dataset.filter]=c.checked);
    f.minNutri=$('#min-nutri').value; f.minEco=$('#min-eco').value;
    // numeric sliders: null = "off" (at the extreme), otherwise the threshold
    const sv=(id, offWhen, off)=>{ const el=$(id); if(!el) return null; const v=+el.value; return offWhen(v)?null:v; };
    f.max_sugar  = sv('#sl-sugar',   v=>v>=50, 50);
    f.min_protein= sv('#sl-protein', v=>v<=0, 0);
    f.max_salt   = sv('#sl-salt',    v=>v>=5, 5);
    f.max_satfat = sv('#sl-satfat',  v=>v>=30, 30);
    f.max_energy = sv('#sl-energy',  v=>v>=600, 600);
    f.min_fibre  = sv('#sl-fibre',   v=>v<=0, 0);
    return f;
  }
  function passesFiltersClient(p){
    const f=readFilters(), n=p.nutrients;
    if(state.allergens.size && p.allergens.some(a=>state.allergens.has(a))) return false;
    if(f.high_protein && n.proteins<8) return false;
    if(f.low_sugar && n.sugars>5) return false;
    if(f.low_salt && n.salt>0.3) return false;
    if(f.low_satfat && n.saturated_fat>3) return false;
    if(f.high_fibre && n.fiber<3) return false;
    if(f.low_calorie && n.energy_kcal>150) return false;
    if(f.low_co2 && p.eco_metrics.co2_kg>2) return false;
    if(f.organic && !p.organic) return false;
    if(f.few_additives && !((p.additives_n===0)||(p.nova&&p.nova<=2))) return false;
    const order={a:1,b:2,c:3,d:4,e:5};
    if(f.minNutri && order[p.nutriscore]>order[f.minNutri.toLowerCase()]) return false;
    if(f.minEco && order[p.ecoscore]>order[f.minEco.toLowerCase()]) return false;
    if(f.max_sugar!=null && n.sugars>f.max_sugar) return false;
    if(f.min_protein!=null && n.proteins<f.min_protein) return false;
    if(f.max_salt!=null && n.salt>f.max_salt) return false;
    if(f.max_satfat!=null && n.saturated_fat>f.max_satfat) return false;
    if(f.max_energy!=null && n.energy_kcal>f.max_energy) return false;
    if(f.min_fibre!=null && n.fiber<f.min_fibre) return false;
    return true;
  }
  function onFilterChange(){ if(state.current!=null) refreshRecommendation(); else renderResults(); }
  function resetFilters(){
    document.querySelectorAll('[data-filter]').forEach(c=>c.checked=false);
    $('#min-nutri').value=''; $('#min-eco').value='';
    document.querySelectorAll('.nslider').forEach(sl=>{ sl.value = sl.dataset.dir==='min'?0:sl.dataset.off;
      sl.dispatchEvent(new Event('input')); });
    onFilterChange();
  }
  function setWeight(pct){
    state.weight = pct/100;
    if($('#acc-priority')){ $('#acc-priority').value=pct; $('#acc-prio-health').textContent=pct+'%'; $('#acc-prio-eco').textContent=(100-pct)+'%'; }
  }

  /* ---------------------------------------------------------- allergens (account only) */
  function renderAllergenChips(){
    const preset = state.allergensAvailable.map(a=>`<span class="chip ${state.allergens.has(a)?'on':''}" onclick="App.toggleAllergen('${esc(a)}')">${esc(a)}</span>`).join('');
    if($('#acc-allergen-chips')) $('#acc-allergen-chips').innerHTML=preset || '<span class="muted">No preset allergens in this dataset.</span>';
    const customs=[...state.allergens].filter(a=>!state.allergensAvailable.includes(a));
    if($('#acc-allergen-custom')) $('#acc-allergen-custom').innerHTML = customs.map(a=>`<span class="chip on custom" onclick="App.toggleAllergen('${esc(a)}')">${esc(a)} &times;</span>`).join('');
  }
  function toggleAllergen(a){ a=(a||'').trim().toLowerCase(); if(!a) return; if(state.allergens.has(a)) state.allergens.delete(a); else state.allergens.add(a); renderAllergenChips(); }
  function addAllergenText(){
    const inp=$('#allergen-input'); if(!inp) return; const val=(inp.value||'').trim().toLowerCase(); if(!val) return;
    state.allergens.add(val); inp.value=''; renderAllergenChips();
    if(!state.allergensAvailable.includes(val)) toast(`Added "${val}". It filters products only if it matches a detected allergen name.`);
  }

  /* ---------------------------------------------------------- account */
  function renderAccount(){
    const anon=$('#account-anon'), u=$('#account-user');
    if(state.user){ anon.hidden=true; u.hidden=false; $('#acc-name').textContent=state.user;
      const ob=$('#onboard-banner'); if(ob) ob.hidden = !needsOnboarding();
      setWeight(Math.round((state.profile?.health_weight??0.7)*100));
      $('#tg-health').checked=state.showHealth; $('#tg-eco').checked=state.showEco;
      renderAllergenChips(); }
    else { anon.hidden=false; u.hidden=true; }
  }
  function onToggleChange(){
    state.showHealth=$('#tg-health').checked; state.showEco=$('#tg-eco').checked;
    if(!state.showHealth && !state.showEco){ toast('Keep at least one — enabling both.'); state.showHealth=state.showEco=true; $('#tg-health').checked=$('#tg-eco').checked=true; }
  }
  let authMode='register';
  function authTab(m){ authMode=m;
    $('#tab-login').classList.toggle('active',m==='login'); $('#tab-register').classList.toggle('active',m==='register');
    $('#auth-submit').textContent = m==='login'?'Sign in':'Create account'; $('#auth-msg').textContent='';
  }
  function submitAuth(){
    const username=$('#auth-user').value, password=$('#auth-pass').value, msg=$('#auth-msg');
    const url = authMode==='login'?'/api/login':'/api/register';
    api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})})
      .then(r=>{ if(r.ok){ msg.className='auth-msg ok'; msg.textContent=r.message;
                   loadMe().then(()=>{ applyGateUI(); renderAccount();
                     if(needsOnboarding()){ toast('Welcome! Set your preferences below to start.'); go('account'); }
                     else { toast('Welcome back, '+state.user); go('discover'); } }); }
                 else { msg.className='auth-msg'; msg.textContent=r.message; } });
  }
  function logout(){ api('/api/logout',{method:'POST'}).then(()=>{ state.user=null;state.profile=null;state.favorites=new Set();state.allergens=new Set();
    renderAllergenChips(); updateAccountLabel(); applyGateUI(); renderAccount(); go('account'); toast('Signed out'); }); }
  function savePrefs(){
    onToggleChange();
    api('/api/preferences',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({allergens:[...state.allergens], health_weight: state.weight, show_health: state.showHealth, show_eco: state.showEco})})
      .then(r=>{ const wasOnboarding = needsOnboarding(); state.profile=r.profile;
        const f=$('#save-flash'); f.hidden=false; setTimeout(()=>f.hidden=true,1800);
        const ob=$('#onboard-banner'); if(ob) ob.hidden=true;
        if(wasOnboarding){ toast('All set! Taking you to search…'); setTimeout(()=>go('discover'), 700); }
        else toast('Preferences saved — applied to all results');
      });
  }
  function updateAccountLabel(){ $('#account-label').textContent = state.user? state.user : 'Sign in'; }
  function loadMe(){
    return api('/api/me').then(r=>{
      state.user=r.user; state.profile=r.profile||null;
      if(state.profile){ state.allergens=new Set(state.profile.allergens); setWeight(Math.round(state.profile.health_weight*100));
        state.showHealth=state.profile.show_health!==false; state.showEco=state.profile.show_eco!==false;
        state.favorites=new Set(state.profile.favorites); }
      updateAccountLabel(); applyGateUI();
    });
  }

  /* ---------------------------------------------------------- insights */
  function loadOverview(){
    if(state.overviewLoaded) return;
    api('/api/overview').then(o=>{
      state.overviewLoaded=true;
      $('#stat-row').innerHTML = [
        [o.total, 'products in catalogue'],
        [o.categories_n, 'food categories'],
        [o.with_image, 'with product photos'],
        [o.model_accuracy+'%', 'model accuracy (5-fold CV)'],
      ].map(s=>`<div class="stat"><div class="num">${s[0]}</div><div class="lab">${s[1]}</div></div>`).join('');
      const gl=['A','B','C','D','E'];
      Charts.bar('c-nutri', gl, gl.map(g=>o.nutriscore_dist[g.toLowerCase()]||0), {gradeColors:true, unit:' products'});
      Charts.bar('c-eco', gl, gl.map(g=>o.ecoscore_dist[g.toLowerCase()]||0), {gradeColors:true, unit:' products'});
      Charts.doughnut('c-cat', Object.keys(o.category_dist), Object.values(o.category_dist));
      Charts.bar('c-sugar', gl, gl.map(g=>o.sugar_by_grade[g.toLowerCase()]||0), {gradeColors:true, unit:' g'});
      Charts.bar('c-co2', gl, gl.map(g=>o.co2_by_eco[g.toLowerCase()]||0), {gradeColors:true, unit:' kg'});
      Charts.bar('c-imp', Object.keys(o.feature_importance), Object.values(o.feature_importance), {horizontal:true, colors:'#4f9d6e'});
      if(o.shap_importance && Object.keys(o.shap_importance).length)
        Charts.bar('c-shap', Object.keys(o.shap_importance), Object.values(o.shap_importance), {horizontal:true, colors:'#7c5cbf'});
      if(o.eco_feature_importance && Object.keys(o.eco_feature_importance).length)
        Charts.bar('c-eco-imp', Object.keys(o.eco_feature_importance), Object.values(o.eco_feature_importance), {horizontal:true, colors:'#3a7355'});
    });
  }

  /* ---------------------------------------------------------- init */
  function init(){
    const input=$('#search-input');
    input.addEventListener('input', e=>{ $('.searchbar').classList.toggle('has-text', !!e.target.value); suggest(e.target.value); });
    input.addEventListener('focus', ()=>{ if(!input.value) historyDropdown(); });
    input.addEventListener('keydown', onSearchKey);
    document.addEventListener('click', e=>{ if(!e.target.closest('.searchwrap')) hideAC(); });
    document.querySelectorAll('[data-filter]').forEach(c=>c.addEventListener('change', onFilterChange));
    $('#min-nutri').addEventListener('change', onFilterChange);
    $('#min-eco').addEventListener('change', onFilterChange);
    // nutrient range sliders: update the readout on input, re-filter live
    document.querySelectorAll('.nslider').forEach(sl=>{
      const out=document.querySelector('#'+sl.id+'-out');
      const render=()=>{ if(out){ const v=+sl.value; const off=sl.dataset.off;
        out.textContent = (sl.dataset.dir==='min' ? (v<=0?'any':'\u2265 '+v+sl.dataset.unit)
                                                  : (v>=+off?'any':'\u2264 '+v+sl.dataset.unit)); } };
      sl.addEventListener('input', render);
      sl.addEventListener('change', onFilterChange);
      render();
    });
    if($('#acc-priority')) $('#acc-priority').addEventListener('input', e=>setWeight(+e.target.value));
    if($('#tg-health')) $('#tg-health').addEventListener('change', onToggleChange);
    if($('#tg-eco')) $('#tg-eco').addEventListener('change', onToggleChange);
    if($('#allergen-input')) $('#allergen-input').addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); addAllergenText(); } });
    document.addEventListener('keydown', e=>{ if(e.key==='Escape'){ if(!$('#chart-zoom').hidden) closeZoom(); else if(!$('#detail-modal').hidden) closeDetail(); } });
    api('/api/overview').then(o=>{ state.allergensAvailable=o.allergens_available||[]; })
      .then(loadMe)
      .then(()=>{ renderAllergenChips(); if(gated()) go('account'); else go('discover'); });
    renderResults();
  }

  return { go, toggleNav, runSearch, openProduct, openDetail, closeDetail, pickHistory, openFromSuggest, removeHistory,
           backToResults, toggleFav, resetFilters, toggleAllergen, addAllergenText, selectShapGrade, onToggleChange,
           zoomChart, closeZoom,
           authTab, submitAuth, logout, savePrefs, init, imgFallback,
           clearSearch:()=>{ $('#search-input').value=''; $('.searchbar').classList.remove('has-text'); hideAC(); } };
})();

document.addEventListener('DOMContentLoaded', App.init);
