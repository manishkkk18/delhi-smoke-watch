// Section 4: the monsoon's northern limit (NLM) on successive dates in 2026, and arrival vs normal in 140 cities.
import { esc, fmtDate, placeTip, projection, tok } from "./common.js";

const daysBetween = (a, b) => Math.round((new Date(b) - new Date(a)) / 864e5);

export function initOnset({ topo, onset }) {
  const states = topojson.feature(topo, topo.objects.states).features;
  const box = document.getElementById("onset-map"), fig = box.parentElement, tip = document.getElementById("onset-tip");
  const W = 800, H = 860;
  const proj = projection(states, W, H);
  const path = d3.geoPath(proj);
  // NLM lines over land only matter from Kerala onset on; keep the earlier sea-only positions out of the stepper
  const lines = onset.lines.filter((l) => l.coords.length > 1 && l.date >= onset.kerala.onset);
  const cities = onset.cities.filter((c) => c.lonlat && c.arrived);

  const svg = d3.select(box).append("svg").attr("viewBox", `0 0 ${W} ${H}`);
  const defs = svg.append("defs");
  defs.append("clipPath").attr("id", "india-clip").append("path").attr("d", path({ type: "FeatureCollection", features: states }));
  svg.append("g").selectAll("path").data(states).join("path").attr("d", path).attr("fill", "#fffdf8")
    .attr("stroke", tok("--rule")).attr("stroke-width", 0.8);
  const covered = svg.append("path").attr("clip-path", "url(#india-clip)").attr("fill", tok("--rain-soft"));
  svg.append("path").datum(topojson.mesh(topo, topo.objects.states, (a, b) => a === b)).attr("d", path)
    .attr("fill", "none").attr("stroke", tok("--ink")).attr("stroke-width", 1.1);

  const dates = lines.map((l) => l.date);
  const shade = d3.scaleLinear().domain([0, Math.max(1, lines.length - 1)]).range([0.25, 1]);
  const lineGen = (l) => d3.line()(l.coords.map((c) => proj(c)));
  const nlm = svg.append("g").attr("fill", "none").selectAll("path").data(lines).join("path")
    .attr("d", lineGen).attr("stroke", tok("--rain")).attr("stroke-linejoin", "round").attr("stroke-linecap", "round");
  const nlmLabel = svg.append("text").attr("class", "lbl-strong paper-halo");

  // cities: diverging by days late (teal early, ochre/brown late), neutral within ±2 days
  const lateMax = Math.max(10, d3.max(cities, (c) => Math.abs(c.days_late)));
  const color = (d) => (Math.abs(d) <= 2 ? tok("--c-n") : d < 0
    ? d3.interpolateRgb(tok("--c-e"), tok("--c-le"))(Math.min(1, (-d - 2) / (lateMax - 2)))
    : d3.interpolateRgb(tok("--c-d"), tok("--c-ld"))(Math.min(1, (d - 2) / (lateMax - 2))));
  const dots = svg.append("g").selectAll("circle").data(cities).join("circle")
    .attr("cx", (c) => proj(c.lonlat)[0]).attr("cy", (c) => proj(c.lonlat)[1]).attr("r", 6)
    .attr("fill", (c) => color(c.days_late)).attr("stroke", tok("--ink")).attr("stroke-width", 0.8)
    .on("pointermove", (e, c) => {
      tip.innerHTML = `<b>${esc(c.city)}</b>, ${esc(c.state)}<br>Arrived ${fmtDate(c.arrived)} · normal ${fmtDate(c.normal)}<br>${
        c.days_late === 0 ? "On time" : `${Math.abs(c.days_late)} days ${c.days_late > 0 ? "late" : "early"}`}`;
      placeTip(tip, fig, e);
    })
    .on("pointerleave", () => { tip.hidden = true; });
  // hit area for touch: larger invisible circles
  dots.clone().attr("r", 14).attr("fill", "transparent").attr("stroke", "none").lower();

  const slider = document.getElementById("nlm");
  slider.max = lines.length - 1; slider.value = lines.length - 1;
  function draw(k) {
    const l = lines[k];
    nlm.attr("stroke-width", (_, i) => (i === k ? 3 : 1)).attr("stroke-opacity", (_, i) => (i <= k ? shade(i) * (i === k ? 1 : 0.55) : 0));
    const c = l.coords;
    // the monsoon covers what lies south/east of the line (same rule as scripts/onset.py close_ring):
    // lines ending past 25°N close north to 40°N then east; others close east along their last latitude
    const end = c[c.length - 1];
    const tail = end[1] > 25 ? [[end[0], 40], [100, 40]] : [[100, end[1]]];
    const ring = [...c, ...tail, [100, 0], [c[0][0], 0], c[0]];
    let poly = { type: "Polygon", coordinates: [ring] };
    if (d3.geoArea(poly) > 2 * Math.PI) poly = { type: "Polygon", coordinates: [ring.slice().reverse()] }; // d3 winding
    covered.attr("d", path(poly));
    dots.attr("opacity", (d) => (d.arrived <= l.date ? 1 : 0.28));
    const inside = c.map((p) => proj(p)).filter(([x, y]) => x > 20 && x < W - 60 && y > 20 && y < H - 20);
    const anchor = inside.length ? inside[0] : proj(c[0]);
    nlmLabel.attr("x", Math.max(8, anchor[0])).attr("y", anchor[1] - 10).text(fmtDate(l.date));
    document.getElementById("nlm-label").textContent = `Northern limit on ${fmtDate(l.date)}`;
    slider.setAttribute("aria-valuetext", `Northern limit of the monsoon on ${fmtDate(l.date)}`);
  }
  slider.addEventListener("input", () => draw(+slider.value));
  draw(lines.length - 1);

  const k = onset.kerala, all = onset.all_india;
  const late = (a, n) => { const d = daysBetween(n, a); return d === 0 ? "on the normal date" : `${Math.abs(d)} day${Math.abs(d) > 1 ? "s" : ""} ${d > 0 ? "late" : "early"}`; };
  document.getElementById("onset-stats").innerHTML = `
    <div class="stat"><b>${fmtDate(k.onset)}</b><span>Onset over Kerala, ${late(k.onset, k.normal)} (normal ${fmtDate(k.normal)})</span></div>
    <div class="stat"><b>${fmtDate(all.covered)}</b><span>Covered all of India, ${late(all.covered, all.normal)} (normal ${fmtDate(all.normal)})</span></div>`;
  const lateCities = cities.filter((c) => c.days_late > 2).length, earlyCities = cities.filter((c) => c.days_late < -2).length;
  document.getElementById("onset-lede").textContent =
    `The rains reached Kerala ${late(k.onset, k.normal)} and had covered the whole country ${late(all.covered, all.normal)}. ` +
    `In between, of ${cities.length} cities with an IMD normal date, ${lateCities} got the monsoon more than two days late and ${earlyCities} more than two days early. Drag through the dates to follow the line north.`;
  document.getElementById("onset-legend").innerHTML = `
    <p class="chart-title">Cities: arrival against normal</p>
    <div class="ramp" style="background:linear-gradient(90deg, ${tok("--c-le")}, ${tok("--c-e")} 40%, ${tok("--c-n")} 50%, ${tok("--c-d")} 60%, ${tok("--c-ld")})"></div>
    <div class="ramp-ends"><span>${lateMax} days early</span><span>on time</span><span>${lateMax} days late</span></div>
    <p class="chart-title" style="margin-top:14px">Lines</p>
    <div class="legend-inline"><span><svg width="26" height="8"><line x1="0" x2="26" y1="4" y2="4" stroke="${tok("--rain")}" stroke-width="3"/></svg>Northern limit on the chosen date</span>
    <span><svg width="26" height="12"><rect width="26" height="12" rx="2" fill="${tok("--rain-soft")}"/></svg>Area the monsoon had covered</span></div>`;
  document.getElementById("onset-note").innerHTML =
    `Lines: the “northern limit of monsoon” IMD published on each day it advanced (${lines.length} positions from ${fmtDate(dates[0])}). ` +
    `City arrival = the first published line north of the city. Normal dates: IMD’s 1961–2019 normals for ${cities.length} cities (IMD publishes the normal isochrones only as a map figure, so they are shown as city dates, not lines).`;
}
