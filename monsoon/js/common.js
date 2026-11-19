// Shared helpers: data loading, IMD categories, colours (read from the CSS tokens), formatting.
const css = getComputedStyle(document.documentElement);
export const tok = (name) => css.getPropertyValue(name).trim();

export const CATS = [
  { key: "LE", label: "Large excess", range: "+60% or more", color: tok("--c-le") },
  { key: "E", label: "Excess", range: "+20% to +59%", color: tok("--c-e") },
  { key: "N", label: "Normal", range: "−19% to +19%", color: tok("--c-n") },
  { key: "D", label: "Deficient", range: "−20% to −59%", color: tok("--c-d") },
  { key: "LD", label: "Large deficient", range: "−60% to −99%", color: tok("--c-ld") },
  { key: "NR", label: "No rain", range: "−100%", color: tok("--c-nr"), fill: "url(#hatch-nr)" },
];
export const MISSING = { key: "missing", label: "No data", range: "", color: tok("--c-missing"), fill: "url(#hatch-missing)" };
export const CAT = Object.fromEntries([...CATS, MISSING].map((c) => [c.key, c]));

// IMD's buckets (same rounding as scripts/common.py)
export function category(dep) {
  if (dep == null || Number.isNaN(dep)) return "missing";
  if (dep <= -99.5) return "NR";
  if (dep <= -59.5) return "LD";
  if (dep <= -19.5) return "D";
  if (dep < 19.5) return "N";
  if (dep < 59.5) return "E";
  return "LE";
}
export const fillFor = (dep) => { const c = CAT[category(dep)]; return c.fill || c.color; };

const cache = new Map();
export function load(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(`data/${path}`).then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path);
}

export const fmtPct = (d) => (d == null ? "no data" : `${d > 0 ? "+" : d < 0 ? "−" : "±"}${Math.abs(d)}%`);
export const fmtMm = (v) => (v == null ? "–" : `${d3.format(",")(Math.round(v))} mm`);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const fmtDate = (iso) => { const [, m, d] = iso.split("-").map(Number); return `${d} ${MONTHS[m - 1]}`; };
export const slug = (s) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Hatch patterns used for "No rain" and "No data"; added once per SVG. */
export function addPatterns(svg) {
  const defs = svg.append("defs");
  const p1 = defs.append("pattern").attr("id", "hatch-nr").attr("patternUnits", "userSpaceOnUse").attr("width", 5).attr("height", 5).attr("patternTransform", "rotate(45)");
  p1.append("rect").attr("width", 5).attr("height", 5).attr("fill", tok("--c-nr"));
  p1.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 5).attr("stroke", tok("--c-d")).attr("stroke-width", 1.2);
  const p2 = defs.append("pattern").attr("id", "hatch-missing").attr("patternUnits", "userSpaceOnUse").attr("width", 5).attr("height", 5).attr("patternTransform", "rotate(-45)");
  p2.append("rect").attr("width", 5).attr("height", 5).attr("fill", "#fffdf8");
  p2.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 5).attr("stroke", tok("--past")).attr("stroke-width", 1);
  return defs;
}

export function swatch(key) {
  const c = CAT[key];
  if (key === "NR") return `background: repeating-linear-gradient(45deg, ${c.color} 0 3px, ${tok("--c-d")} 3px 4px)`;
  if (key === "missing") return `background: repeating-linear-gradient(-45deg, #fffdf8 0 3px, ${tok("--past")} 3px 4px)`;
  return `background:${c.color}`;
}

/** India projection fitted to a box. */
export function projection(features, w, h, pad = 8) {
  return d3.geoConicConformal().parallels([12, 28]).rotate([-80, 0])
    .fitExtent([[pad, pad], [w - pad, h - pad]], { type: "FeatureCollection", features });
}

/** Position a tooltip inside its figure, near the pointer. */
export function placeTip(tip, fig, event) {
  const r = fig.getBoundingClientRect();
  let x = event.clientX - r.left + 14, y = event.clientY - r.top + 14;
  tip.hidden = false;
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  if (x + tw > r.width) x = event.clientX - r.left - tw - 14;
  if (y + th > r.height) y = event.clientY - r.top - th - 14;
  tip.style.left = `${Math.max(0, x)}px`;
  tip.style.top = `${Math.max(0, y)}px`;
}

export const bus = new EventTarget(); // "select" events: detail = district id
