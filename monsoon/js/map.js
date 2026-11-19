// Section 2: animated district choropleth of cumulative departure, with play/pause and a week scrubber.
import { CATS, CAT, MISSING, addPatterns, bus, category, esc, fillFor, fmtDate, fmtMm, fmtPct, placeTip, projection, swatch, tok } from "./common.js";

export function initMap({ topo, weekly, check }) {
  const districts = topojson.feature(topo, topo.objects.districts).features;
  const stateMesh = topojson.mesh(topo, topo.objects.states, (a, b) => a !== b);
  const outline = topojson.mesh(topo, topo.objects.states, (a, b) => a === b);
  const box = document.getElementById("choropleth");
  const fig = box.parentElement;
  const tip = document.getElementById("map-tip");
  const W = 800, H = 860;
  const proj = projection(districts, W, H);
  const path = d3.geoPath(proj);
  const weeks = weekly.weeks;
  let week = weeks.length - 1, selected = null, timer = null;

  const svg = d3.select(box).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("preserveAspectRatio", "xMidYMid meet");
  addPatterns(svg);
  const g = svg.append("g");
  const shapes = g.append("g").selectAll("path").data(districts).join("path")
    .attr("class", "district").attr("d", path)
    .attr("stroke", "#fffdf8").attr("stroke-width", 0.35).attr("vector-effect", "non-scaling-stroke")
    .attr("tabindex", -1);
  g.append("path").datum(stateMesh).attr("d", path).attr("fill", "none").attr("stroke", tok("--ink")).attr("stroke-opacity", 0.55)
    .attr("stroke-width", 0.8).attr("vector-effect", "non-scaling-stroke").attr("pointer-events", "none");
  g.append("path").datum(outline).attr("d", path).attr("fill", "none").attr("stroke", tok("--ink")).attr("stroke-width", 1.1)
    .attr("vector-effect", "non-scaling-stroke").attr("pointer-events", "none");
  // districts where this estimate and IMD's own station figure are 2+ categories apart
  const flagged = districts.filter((d) => check?.districts[d.properties.id]?.flag);
  g.append("path").datum({ type: "FeatureCollection", features: flagged }).attr("d", path).attr("fill", "none")
    .attr("stroke", tok("--ink")).attr("stroke-width", 1.2).attr("stroke-dasharray", "3 2")
    .attr("vector-effect", "non-scaling-stroke").attr("pointer-events", "none");
  const selLayer = g.append("path").attr("fill", "none").attr("stroke", tok("--ink")).attr("stroke-width", 2.4)
    .attr("vector-effect", "non-scaling-stroke").attr("pointer-events", "none");

  const depOf = (d, i = week) => weekly.districts[d.properties.id]?.d?.[i] ?? null;

  function paint(animate) {
    // colours fade between weeks; hatch patterns (url fills) can't be interpolated, so they switch directly
    const isUrl = (v) => String(v).startsWith("url");
    const fade = animate ? shapes.filter(function (d) { return !isUrl(this.getAttribute("fill")) && !isUrl(fillFor(depOf(d))); }) : null;
    const faded = new Set(fade ? fade.nodes() : []);
    shapes.filter(function () { return !faded.has(this); }).interrupt().attr("fill", (d) => fillFor(depOf(d)));
    if (fade) fade.transition().duration(380).attr("fill", (d) => fillFor(depOf(d)));
    document.getElementById("week-label").textContent =
      week === weeks.length - 1 ? `Whole season: 1 Jun – 30 Sep` : `Season so far: 1 Jun – ${fmtDate(weeks[week])}`;
    const slider = document.getElementById("week");
    slider.value = week;
    slider.setAttribute("aria-valuetext", `Week ending ${fmtDate(weeks[week])}`);
    legend();
    if (selected) showPick(selected);
  }

  // legend doubles as a count of districts in each category this week
  function legend() {
    const counts = {};
    for (const d of districts) { const c = category(depOf(d)); counts[c] = (counts[c] || 0) + 1; }
    const max = Math.max(...Object.values(counts));
    const rows = [...CATS, MISSING].filter((c) => c.key !== "missing" || counts.missing);
    document.getElementById("legend").innerHTML = rows.map((c) => `
      <div class="leg-row"><span class="leg-sw" style="${swatch(c.key)}"></span>
        <span>${c.label} <span class="range">${c.range}</span></span><span class="leg-count">${counts[c.key] || 0}</span>
        <span class="leg-bar" aria-hidden="true"><i style="width:${((counts[c.key] || 0) / max) * 100}%"></i></span></div>`).join("")
      + `<p class="note" style="margin:4px 0 0">Number of districts in each category, of ${districts.length}.</p>`
      + (flagged.length ? `<div class="leg-row" style="margin-top:6px"><span class="leg-sw" style="background:#fffdf8;border:1.5px dashed ${tok("--ink")}"></span><span class="note" style="grid-column:2/4;margin:0">Estimate disagrees with IMD’s own district figure (${flagged.length} districts)</span></div>` : "");
  }

  function info(d) {
    const rec = weekly.districts[d.properties.id] || {};
    const dep = depOf(d);
    return { name: d.properties.name, state: d.properties.state, dep, cat: CAT[category(dep)], season: rec };
  }

  function showPick(d) {
    const i = info(d);
    const whole = week === weeks.length - 1;
    document.getElementById("map-pick").innerHTML = `
      <h3>${esc(i.name)}</h3><p class="card-state">${esc(i.state)}</p>
      <p class="dep" style="color:${i.dep != null && i.dep < 0 ? tok("--dry") : tok("--rain")}">${fmtPct(i.dep)}</p>
      <span class="chip"><i style="${swatch(i.cat.key)}"></i>${i.cat.label}</span>
      ${check?.districts[d.properties.id]?.flag ? `<p class="note"><b>Low confidence here:</b> IMD’s own figure to ${fmtDate(check.period.slice(-10))} was ${fmtPct(check.districts[d.properties.id].imd)}.</p>` : ""}
      <p class="note">${whole ? "Whole season" : `1 Jun – ${fmtDate(weeks[week])}`}, against the 1971–2020 normal.
        ${whole && i.season.a != null ? `${fmtMm(i.season.a)} fell; ${fmtMm(i.season.n)} is normal.` : ""}</p>
      <a class="btn" href="#district" data-open="${esc(d.properties.id)}">Open the full season →</a>`;
  }

  function select(d, { scroll = false } = {}) {
    selected = d;
    selLayer.attr("d", d ? path(d) : null);
    if (d) showPick(d);
    if (d && scroll) bus.dispatchEvent(new CustomEvent("select", { detail: d.properties.id }));
  }

  document.getElementById("map-pick").addEventListener("click", (e) => {
    const a = e.target.closest("[data-open]");
    if (a) bus.dispatchEvent(new CustomEvent("select", { detail: a.dataset.open }));
  });

  shapes
    .on("pointermove", (e, d) => {
      if (e.pointerType !== "mouse") return;
      const i = info(d);
      tip.innerHTML = `<b>${esc(i.name)}</b>, ${esc(i.state)}<br>${fmtPct(i.dep)} · ${i.cat.label}`;
      placeTip(tip, fig, e);
    })
    .on("pointerleave", () => { tip.hidden = true; })
    .on("click", (e, d) => select(d));

  // zoom & pan (pinch on phones; buttons for everyone)
  const zoom = d3.zoom().scaleExtent([1, 12]).translateExtent([[0, 0], [W, H]])
    .on("zoom", (e) => g.attr("transform", e.transform));
  svg.call(zoom).on("dblclick.zoom", null);
  fig.querySelector(".map-zoom").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const t = svg.transition().duration(300);
    if (b.dataset.zoom === "in") zoom.scaleBy(t, 1.6);
    else if (b.dataset.zoom === "out") zoom.scaleBy(t, 1 / 1.6);
    else zoom.transform(t, d3.zoomIdentity);
  });

  // player
  const play = document.getElementById("play");
  const slider = document.getElementById("week");
  slider.max = weeks.length - 1;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function stop() { clearInterval(timer); timer = null; play.setAttribute("aria-pressed", "false"); play.setAttribute("aria-label", "Play the season"); }
  play.addEventListener("click", () => {
    if (timer) return stop();
    if (week === weeks.length - 1) week = 0;
    play.setAttribute("aria-pressed", "true"); play.setAttribute("aria-label", "Pause");
    paint(!reduce);
    timer = setInterval(() => {
      if (week >= weeks.length - 1) return stop();
      week += 1; paint(!reduce);
    }, reduce ? 1200 : 700);
  });
  slider.addEventListener("input", () => { stop(); week = +slider.value; paint(false); });

  paint(false);

  return {
    focus(id) {
      const d = districts.find((f) => f.properties.id === id);
      if (d) select(d);
    },
    districts,
  };
}
