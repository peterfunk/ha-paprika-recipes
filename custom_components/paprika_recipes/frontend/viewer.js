/* viewer.js - <paprika-viewer>: a read-only recipe browser/reader.
 *
 * It knows nothing about where recipes come from. Give it a `provider`:
 *   {
 *     listRecipes(): Promise<Summary[]>,
 *     getRecipe(uid): Promise<Recipe>,
 *     photoUrl(item): string | null | Promise<string | null>,
 *   }
 * so the same component can run standalone (fetching the sync service's JSON)
 * and later inside Home Assistant. All recipe text is untrusted (it comes from
 * arbitrary websites) and is only ever inserted as text, never as HTML.
 */
import { scaleLine, scaleFirstNumber, formatFactor, formatNumber, parseDirections, splitLines } from "./scale.js";

const CSS = `
:host{display:block;height:100%;overflow:auto;container-type:inline-size;
  --bg:#121214;--fg:#f2f2f3;--muted:#a0a0a8;--card:#1d1d21;--line:#2c2c32;--accent:#f2473a;--accent-fg:#fff;--zoom:1;
  background:var(--bg);color:var(--fg)}
@media (prefers-color-scheme:light){:host(:not([theme=dark])){--bg:#fafafa;--fg:#1b1b1f;--muted:#666a73;--card:#fff;--line:#e0e0e6}}
:host([theme=light]){--bg:#fafafa;--fg:#1b1b1f;--muted:#666a73;--card:#fff;--line:#e0e0e6}
*{box-sizing:border-box}
.root{--base:18px;min-height:100%;padding:1rem 1.1rem 3rem;font:calc(var(--base)*var(--zoom))/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  -webkit-text-size-adjust:100%}
@container (min-width:800px){.root{--base:22px}}
:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.bar{display:flex;gap:.6rem;align-items:center;margin-bottom:.9rem}
.bar h1{font-size:1.4em;margin:0;flex:0 0 auto}
.bar .grow{flex:1;min-width:0}
.search{width:100%;font:inherit;padding:.55em 1em;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.btn{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:.4em 1em;min-height:2.6em;cursor:pointer;white-space:nowrap}
.btn.icon{width:2.6em;padding:0;display:inline-flex;align-items:center;justify-content:center}
.btn svg{width:1.3em;height:1.3em}
.btn[aria-pressed=true],.btn.primary,.chip[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
.chips{display:flex;gap:.5rem;overflow-x:auto;padding-bottom:.5rem;margin-bottom:.8rem;scrollbar-width:none}
@container (min-width:700px){.chips{flex-wrap:wrap;overflow:visible}}
.chip{flex:0 0 auto;font:inherit;font-size:.85em;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:.35em .9em;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}
@container (min-width:500px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@container (min-width:700px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
@container (min-width:1000px){.grid{grid-template-columns:repeat(5,minmax(0,1fr))}}
@container (min-width:1400px){.grid{grid-template-columns:repeat(6,minmax(0,1fr))}}
.grid.list{grid-template-columns:minmax(0,1fr)}
@container (min-width:700px){.grid.list{grid-template-columns:repeat(2,minmax(0,1fr))}}
@container (min-width:1000px){.grid.list{grid-template-columns:repeat(3,minmax(0,1fr))}}
.grid.list button.card{flex-direction:row;align-items:center}
.grid.list .thumb{flex:0 0 4.2em;width:4.2em;aspect-ratio:1}
.grid.list .thumb span{font-size:1.3em}
.grid.list .card-body{padding:.4rem .7rem;min-width:0}
.grid.list .card-title{min-height:0}
button.card{display:flex;flex-direction:column;text-align:left;padding:0;overflow:hidden;border:1px solid var(--line);border-radius:14px;background:var(--card);color:inherit;font:inherit;cursor:pointer}
.thumb{aspect-ratio:3/2;background:linear-gradient(135deg,#34343c,#1d1d21);display:flex;align-items:center;justify-content:center;color:var(--muted);overflow:hidden}
.thumb span{font-size:2em}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.card-body{padding:.45rem .6rem .55rem}
.card-title{font-weight:600;font-size:.9em;line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.5em}
.card-meta{display:flex;flex-direction:column;align-items:flex-start;gap:.15rem;color:var(--muted);font-size:.8em;margin-top:.3rem;min-height:1.2em}
.stars{display:inline-flex;gap:2px;color:var(--accent)}
.stars svg{width:1.05em;height:1.05em}
.msg{color:var(--muted);padding:2.5rem 1rem;text-align:center}
.top{display:grid;grid-template-columns:min(34%,9em) minmax(0,1fr);grid-template-areas:"photo title" "stats stats";gap:.5rem 1rem;align-items:start;margin-bottom:.4rem}
.top.nophoto{grid-template-columns:minmax(0,1fr);grid-template-areas:"title" "stats"}
.photo{grid-area:photo;aspect-ratio:1;border-radius:14px;overflow:hidden;background:var(--card)}
.photo img{width:100%;height:100%;object-fit:cover;display:block}
.titlebox{grid-area:title;min-width:0}
.titlebox h2{margin:0 0 .3rem;font-size:1.5em;line-height:1.2;overflow-wrap:anywhere}
.source,.cats{color:var(--muted);font-size:.9em;margin-top:.25rem;overflow-wrap:anywhere}
.stats{grid-area:stats;display:flex;flex-wrap:wrap;gap:.4rem 1.6rem;margin:.3rem 0 .4rem}
@container (min-width:800px){.top{grid-template-columns:14em minmax(0,1fr);grid-template-areas:"photo title" "photo stats";grid-template-rows:auto 1fr}.top.nophoto{grid-template-areas:"title" "stats";grid-template-rows:auto}.stats{align-self:start;margin-top:.8rem}}
.stat{display:flex;flex-direction:column}
.stat span:first-child{font-size:.7em;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.controls{display:flex;gap:.6rem;align-items:center;margin:.9rem 0 1rem}
.tabs{display:flex;flex:1;background:var(--card);border:1px solid var(--line);border-radius:999px;padding:.2rem}
.tabs button{flex:1;font:inherit;border:0;border-radius:999px;padding:.5em;background:transparent;color:var(--fg);cursor:pointer}
.tabs button[aria-selected=true]{background:var(--accent);color:var(--accent-fg);font-weight:600}
.cols{display:grid;gap:1.6rem}
.pane{display:none}
.root[data-tab=ingredients] .pane-ing,.root[data-tab=directions] .pane-dir{display:block}
@container (min-width:800px){.cols{grid-template-columns:minmax(0,5fr) minmax(0,6fr)}.pane{display:block!important}.tabs{display:none}.controls{justify-content:flex-start}}
.pane h3.sub{font-size:.8em;text-transform:uppercase;letter-spacing:.07em;color:var(--accent);margin:1.3em 0 .3em}
.ing{margin:.6em 0;cursor:pointer}
.ing strong{font-weight:700}
.ing.done,.step.done{opacity:.4;text-decoration:line-through}
ol.steps{counter-reset:s;padding:0;margin:0;list-style:none}
.step{counter-increment:s;display:flex;gap:.7em;margin:.9em 0;cursor:pointer}
.step::before{content:counter(s);flex:0 0 1.9em;height:1.9em;border-radius:50%;background:var(--card);border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-size:.8em;color:var(--muted)}
.more{margin-top:1.4rem;border-top:1px solid var(--line);padding-top:.5rem}
.more summary{cursor:pointer;color:var(--accent);font-weight:600;padding:.4em 0}
.more div{white-space:pre-wrap;margin:.3em 0 .8em;color:var(--fg)}
dialog{border:1px solid var(--line);border-radius:18px;background:var(--card);color:var(--fg);padding:1.2rem;width:min(92%,26em);font:inherit;margin:auto}
dialog::backdrop{background:#000b}
dialog h3{margin:0 0 .8rem;font-size:1.2em}
.presets{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-bottom:1rem}
.stepper{display:flex;align-items:center;justify-content:center;gap:.8rem;margin:.5rem 0 1rem}
.stepper output{min-width:4.5em;text-align:center;font-size:1.5em;font-weight:700}
.preview{text-align:center;color:var(--muted);margin-bottom:1rem;min-height:1.4em}
.actions{display:flex;justify-content:space-between;gap:.6rem}
`;

const SVG_NS = "http://www.w3.org/2000/svg";
function svg(pathD, { fill = "none", stroke = "currentColor", sw = 2 } = {}) {
  const s = document.createElementNS(SVG_NS, "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(SVG_NS, "path");
  p.setAttribute("d", pathD);
  p.setAttribute("fill", fill);
  p.setAttribute("stroke", stroke);
  p.setAttribute("stroke-width", sw);
  p.setAttribute("stroke-linecap", "round");
  p.setAttribute("stroke-linejoin", "round");
  s.append(p);
  return s;
}
const STAR = "M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5-4.8-4.6 6.6-.9z";
const stars = (n) => {
  const w = document.createElement("span");
  w.className = "stars";
  w.setAttribute("role", "img");
  w.setAttribute("aria-label", `${n} of 5 stars`);
  for (let i = 1; i <= 5; i++) w.append(svg(STAR, { fill: i <= n ? "currentColor" : "none", sw: 1.5 }));
  return w;
};

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
  return el;
}

const DENSITY_KEY = "paprika-viewer.density";
const loadDensity = () => { try { return localStorage.getItem(DENSITY_KEY) === "list" ? "list" : "grid"; } catch { return "grid"; } };
const saveDensity = (d) => { try { localStorage.setItem(DENSITY_KEY, d); } catch { /* storage unavailable */ } };
const ZOOM_KEY = "paprika-viewer.zoom";
const loadZoom = () => {
  try { const z = parseFloat(localStorage.getItem(ZOOM_KEY)); return z >= 0.8 && z <= 1.8 ? z : 1; } catch { return 1; }
};
const saveZoom = (z) => { try { localStorage.setItem(ZOOM_KEY, String(z)); } catch { /* storage unavailable */ } };

class PaprikaViewer extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._provider = null;
    this._items = [];
    this._query = "";
    this._filter = "all";
    this._listScroll = 0;
    this._recipe = null;
    this._scale = 1;
    this._zoom = loadZoom();
    this._density = loadDensity();
    this._onHash = () => this._route();
  }

  set provider(p) {
    this._provider = p;
    if (this.isConnected) this._init();
  }

  connectedCallback() {
    if (!this._root) {
      this.shadowRoot.append(h("style", { text: CSS }));
      this._root = h("div", { class: "root" });
      this.shadowRoot.append(this._root);
    }
    this.style.setProperty("--zoom", String(this._zoom));
    if (this.hasAttribute("hash-routing")) window.addEventListener("hashchange", this._onHash);
    if (this._provider) this._init();
  }

  disconnectedCallback() {
    window.removeEventListener("hashchange", this._onHash);
  }

  // ---- data -------------------------------------------------------------
  async _init() {
    this._show(h("div", { class: "msg", text: "Loading recipes…" }));
    try {
      this._items = await this._provider.listRecipes();
    } catch (err) {
      this._show(h("div", { class: "msg" }, h("p", { text: `Could not load recipes (${err.message || err}).` }),
        h("button", { class: "btn", text: "Try again", onclick: () => this._init() })));
      return;
    }
    await this._route();
  }

  async _route() {
    const m = /^#\/r\/(.+)$/.exec(location.hash);
    if (this.hasAttribute("hash-routing") && m) return this._open(decodeURIComponent(m[1]), false);
    this._renderList();
  }

  _show(...nodes) {
    this._root.replaceChildren(...nodes);
  }

  _setPhoto(box, item) {
    if (!item.photo) return false;
    const img = h("img", { alt: "", loading: "lazy", decoding: "async" });
    img.addEventListener("error", () => img.remove());
    box.append(img);
    Promise.resolve(this._provider.photoUrl(item)).then((u) => (u ? (img.src = u) : img.remove())).catch(() => img.remove());
    return true;
  }

  _zoomControls() {
    const step = (d) => () => {
      this._zoom = Math.min(1.8, Math.max(0.8, Math.round((this._zoom + d) * 10) / 10));
      this.style.setProperty("--zoom", String(this._zoom));
      saveZoom(this._zoom);
    };
    return [
      h("button", { class: "btn icon", "aria-label": "Smaller text", text: "A−", onclick: step(-0.1) }),
      h("button", { class: "btn icon", "aria-label": "Larger text", text: "A+", onclick: step(0.1) }),
    ];
  }

  // ---- list view ---------------------------------------------------------
  _renderList() {
    this._recipe = null;
    this._scale = 1;
    const search = h("input", { class: "search", type: "search", placeholder: "Search recipes", "aria-label": "Search recipes", value: this._query });
    search.addEventListener("input", () => { this._query = search.value; this._updateGrid(); });

    const counts = new Map();
    let uncategorized = 0;
    for (const item of this._items) {
      if (!item.categories.length) uncategorized++;
      for (const c of item.categories) counts.set(c, (counts.get(c) || 0) + 1);
    }
    const cats = [...counts.keys()].sort((a, b) => a.localeCompare(b));
    this._chips = h("div", { class: "chips" });
    const filters = [
      ["all", `All (${this._items.length})`],
      ["fav", `Favorites (${this._items.filter((i) => i.favorite).length})`],
      ...cats.map((c) => [`cat:${c}`, `${c} (${counts.get(c)})`]),
      ...(uncategorized ? [["uncat", `Uncategorized (${uncategorized})`]] : []),
    ];
    for (const [key, label] of filters) {
      const b = h("button", { class: "chip", "aria-pressed": String(this._filter === key), text: label, onclick: () => {
        this._filter = key;
        this._chips.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === b)));
        this._updateGrid();
      } });
      this._chips.append(b);
    }
    this._grid = h("div", { class: "grid" + (this._density === "list" ? " list" : "") });
    const densityBtn = h("button", { class: "btn icon", "aria-label": "Compact list", "aria-pressed": String(this._density === "list"), onclick: () => {
      this._density = this._density === "list" ? "grid" : "list";
      saveDensity(this._density);
      densityBtn.setAttribute("aria-pressed", String(this._density === "list"));
      this._grid.classList.toggle("list", this._density === "list");
    } }, svg("M4 6h16M4 12h16M4 18h16", { sw: 2.5 }));
    this._show(
      h("div", { class: "bar" }, h("h1", { text: "Recipes" }), h("div", { class: "grow" }, search), densityBtn, ...this._zoomControls()),
      this._chips, this._grid);
    this._updateGrid();
    this.scrollTop = this._listScroll;
  }

  _updateGrid() {
    const q = this._query.trim().toLowerCase();
    const shown = this._items.filter((i) => {
      if (this._filter === "fav" && !i.favorite) return false;
      if (this._filter === "uncat" && i.categories.length) return false;
      if (this._filter.startsWith("cat:") && !i.categories.includes(this._filter.slice(4))) return false;
      return !q || `${i.name} ${i.categories.join(" ")} ${i.source || ""}`.toLowerCase().includes(q);
    });
    if (!shown.length) return this._grid.replaceChildren(h("div", { class: "msg", text: "No recipes found." }));
    this._grid.replaceChildren(...shown.map((item) => {
      const thumb = h("div", { class: "thumb" });
      if (!this._setPhoto(thumb, item)) thumb.append(h("span", { text: (item.name[0] || "?").toUpperCase() }));
      return h("button", { class: "card", onclick: () => this._open(item.uid, true) }, thumb,
        h("div", { class: "card-body" }, h("div", { class: "card-title", text: item.name }),
          h("div", { class: "card-meta" }, h("span", { text: item.total_time || item.cook_time || "" }), item.rating ? stars(item.rating) : null)));
    }));
  }

  // ---- recipe view -------------------------------------------------------
  async _open(uid, pushHash) {
    if (!this._recipe) this._listScroll = this.scrollTop;
    this._show(h("div", { class: "msg", text: "Loading…" }));
    try {
      this._recipe = await this._provider.getRecipe(uid);
    } catch (err) {
      this._show(h("div", { class: "msg" }, h("p", { text: `Could not load this recipe (${err.message || err}).` }),
        h("button", { class: "btn", text: "Back", onclick: () => this._back() })));
      return;
    }
    this._scale = 1;
    if (pushHash && this.hasAttribute("hash-routing")) {
      window.removeEventListener("hashchange", this._onHash);
      location.hash = `#/r/${encodeURIComponent(uid)}`;
      setTimeout(() => window.addEventListener("hashchange", this._onHash), 0);
    }
    this._renderRecipe();
  }

  _back() {
    if (this.hasAttribute("hash-routing") && location.hash) {
      window.removeEventListener("hashchange", this._onHash);
      history.replaceState(null, "", location.pathname + location.search);
      setTimeout(() => window.addEventListener("hashchange", this._onHash), 0);
    }
    this._renderList();
  }

  _renderRecipe() {
    const r = this._recipe;
    const photoBox = h("div", { class: "photo" });
    const hasPhoto = this._setPhoto(photoBox, r);
    this._statsEl = h("div", { class: "stats" });
    this._scaleBtn = h("button", { class: "btn", onclick: () => this._openScaleDialog() });
    this._ingEl = h("div");
    this._dirEl = h("div");
    const tabBtn = (id, label) => h("button", { role: "tab", "aria-selected": String(id === "ingredients"), text: label, onclick: () => {
      this._root.dataset.tab = id;
      tabs.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.textContent === label)));
    } });
    const tabs = h("div", { class: "tabs", role: "tablist" }, tabBtn("ingredients", "Ingredients"), tabBtn("directions", "Directions"));

    const extras = [["Description", r.description], ["Notes", r.notes], ["Nutrition", r.nutritional_info]]
      .filter(([, t]) => t).map(([label, text]) => h("details", { class: "more", open: label === "Nutrition" ? null : "" },
        h("summary", { text: label }), h("div", { text })));

    this._show(
      h("div", { class: "bar" }, h("button", { class: "btn icon", "aria-label": "Back to recipes", onclick: () => this._back() },
        svg("M15 5l-7 7 7 7", { sw: 2.5 })), h("div", { class: "grow" }), ...this._zoomControls()),
      h("div", { class: "top" + (hasPhoto ? "" : " nophoto") }, hasPhoto ? photoBox : null,
        h("div", { class: "titlebox" }, h("h2", { text: r.name }), r.rating ? stars(r.rating) : null,
          r.source ? h("div", { class: "source", text: r.source }) : null,
          r.categories.length ? h("div", { class: "cats", text: r.categories.join(" · ") }) : null),
        this._statsEl),
      h("div", { class: "controls" }, this._scaleBtn, tabs),
      h("div", { class: "cols" },
        h("section", { class: "pane pane-ing", "aria-label": "Ingredients" }, this._ingEl),
        h("section", { class: "pane pane-dir", "aria-label": "Directions" }, this._dirEl)),
      ...extras);
    this._root.dataset.tab = "ingredients";
    this._renderStats();
    this._renderIngredients();
    this._renderDirections();
    this.scrollTop = 0;
  }

  _renderStats() {
    const r = this._recipe;
    const rows = [["Prep", r.prep_time], ["Cook", r.cook_time], ["Total", r.total_time],
      ["Servings", scaleFirstNumber(r.servings, this._scale)], ["Difficulty", r.difficulty]].filter(([, v]) => v);
    this._statsEl.replaceChildren(...rows.map(([k, v]) => h("div", { class: "stat" }, h("span", { text: k }), h("span", { text: v }))));
    this._scaleBtn.textContent = `Scale ${formatFactor(this._scale)}`;
  }

  _renderIngredients() {
    const nodes = splitLines(this._recipe.ingredients).map((line) => {
      const res = scaleLine(line, this._scale);
      if (res.kind === "header") return h("h3", { class: "sub", text: res.segments[0].text });
      const p = h("p", { class: "ing", onclick: (e) => e.currentTarget.classList.toggle("done") },
        res.segments.map((s) => (s.lead ? h("strong", { text: s.text }) : s.text)));
      return p;
    });
    this._ingEl.replaceChildren(...(nodes.length ? nodes : [h("div", { class: "msg", text: "No ingredients." })]));
  }

  _renderDirections() {
    const items = parseDirections(this._recipe.directions);
    const list = h("ol", { class: "steps" });
    const out = [];
    const flush = () => { if (list.childElementCount) out.push(list.cloneNode(true)); list.replaceChildren(); };
    for (const it of items) {
      if (it.kind === "header") { flush(); out.push(h("h3", { class: "sub", text: it.text })); continue; }
      list.append(h("li", { class: "step", onclick: (e) => e.currentTarget.classList.toggle("done") }, h("span", { text: it.text })));
    }
    flush();
    this._dirEl.replaceChildren(...(out.length ? out : [h("div", { class: "msg", text: "No directions." })]));
  }

  // ---- scale dialog ------------------------------------------------------
  _openScaleDialog() {
    const apply = (f) => {
      this._scale = Math.min(50, Math.max(0.25, Math.round(f * 100) / 100));
      refresh();
      this._renderStats();
      this._renderIngredients();
    };
    const out = h("output", { "aria-live": "polite" });
    const preview = h("div", { class: "preview" });
    const refresh = () => {
      for (const [f, btn] of presetBtns) btn.setAttribute("aria-pressed", String(Math.abs(f - this._scale) < 0.001));
      out.textContent = formatFactor(this._scale);
      const sv = this._recipe.servings ? scaleFirstNumber(this._recipe.servings, this._scale) : "";
      preview.textContent = sv ? `Servings: ${sv}` : "";
    };
    const presets = [[0.5, "½×"], [1, "1×"], [1.5, "1½×"], [2, "2×"], [3, "3×"], [4, "4×"]];
    const presetBtns = presets.map(([f, label]) => [f, h("button", { class: "btn", text: label, onclick: () => apply(f) })]);
    const dlg = h("dialog", { "aria-label": "Scale recipe" },
      h("h3", { text: "Scale recipe" }),
      h("div", { class: "presets" }, presetBtns.map(([, btn]) => btn)),
      h("div", { class: "stepper" },
        h("button", { class: "btn icon", "aria-label": "Decrease", text: "−", onclick: () => apply(this._scale - (this._scale > 2 ? 0.5 : 0.25)) }),
        out,
        h("button", { class: "btn icon", "aria-label": "Increase", text: "+", onclick: () => apply(this._scale + (this._scale >= 2 ? 0.5 : 0.25)) })),
      preview,
      h("div", { class: "actions" }, h("button", { class: "btn", text: "Reset", onclick: () => apply(1) }),
        h("button", { class: "btn primary", autofocus: true, text: "Done", onclick: () => dlg.close() })));
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener("close", () => dlg.remove());
    this._root.append(dlg);
    refresh();
    dlg.showModal();
  }
}

if (!customElements.get("paprika-viewer")) customElements.define("paprika-viewer", PaprikaViewer);
export { PaprikaViewer, formatNumber };
