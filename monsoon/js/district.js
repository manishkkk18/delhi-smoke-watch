// Section 3: search box -> district card with cumulative rain (actual vs normal) and the last five seasons.
import { CAT, bus, category, esc, fmtDate, fmtMm, fmtPct, load, placeTip, slug, swatch, tok } from "./common.js";

const YEARS = ["2021", "2022", "2023", "2024", "2025"];
const norm = (s) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");

/** Accessible combobox over district names + IMD spellings / new-district aliases. */
export function initSearch(index, onPick) {
  for (const form of document.querySelectorAll("[data-search]")) {
    const input = form.querySelector("input");
    const list = document.createElement("ul");
    list.id = `${input.id}-list`; list.setAttribute("role", "listbox"); list.hidden = true;
    form.append(list);
    input.setAttribute("role", "combobox"); input.setAttribute("aria-controls", list.id);
    input.setAttribute("aria-autocomplete", "list"); input.setAttribute("aria-expanded", "false");
    let items = [], active = -1;
    const render = () => {
      list.innerHTML = items.map((it, i) => `<li role="option" id="${list.id}-${i}" aria-selected="${i === active}" data-i="${i}">
        <span>${esc(it.label)}</span><small>${esc(it.sub)}</small></li>`).join("");
      list.hidden = !items.length; input.setAttribute("aria-expanded", String(!!items.length));
      if (active >= 0) input.setAttribute("aria-activedescendant", `${list.id}-${active}`); else input.removeAttribute("aria-activedescendant");
    };
    const choose = (it) => { input.value = it.label; items = []; render(); input.blur(); onPick(it); };
    input.addEventListener("input", () => {
      const q = norm(input.value);
      active = -1;
      if (q.length < 2) { items = []; return render(); }
      const scored = [];
      for (const it of index) {
        const k = it.key.indexOf(q);
        if (k >= 0) scored.push([k === 0 ? 0 : 1, it.label.length, it]);
      }
      scored.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      const seen = new Set();
      items = scored.map((s) => s[2]).filter((it) => !seen.has(it.label + it.id) && seen.add(it.label + it.id)).slice(0, 8);
      if (items.length) active = 0;
      render();
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { active = Math.min(items.length - 1, active + 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = Math.max(0, active - 1); render(); e.preventDefault(); }
      else if (e.key === "Enter") { e.preventDefault(); if (items[active]) choose(items[active]); }
      else if (e.key === "Escape") { items = []; render(); }
    });
    list.addEventListener("pointerdown", (e) => { const li = e.target.closest("li"); if (li) { e.preventDefault(); choose(items[+li.dataset.i]); } });
    input.addEventListener("blur", () => setTimeout(() => { items = []; render(); }, 150));
  }
}

export function buildIndex(districts, aliases) {
  const byId = Object.fromEntries(districts.map((d) => [d.properties.id, d.properties]));
  const idx = districts.map((d) => ({ id: d.properties.id, label: d.properties.name, sub: d.properties.state, key: norm(d.properties.name) }));
  for (const a of aliases) {
    const p = byId[a.id]; if (!p) continue;
    idx.push({ id: a.id, label: a.q, sub: a.note ? `shown as ${p.name}, ${p.state}` : p.state, key: norm(a.q), note: a.note });
  }
  return { idx, byId };
}

export async function showDistrict(id, { byId, weekly, aliasNote, label, check }) {
  const card = document.getElementById("card");
  const p = byId[id];
  if (!p) { card.innerHTML = `<p class="muted">That district isn't on the map.</p>`; return; }
  const series = (await load(`series/${slug(p.state)}.json`)).districts[id];
  const weeks = weekly.weeks;
  const rec = weekly.districts[id] || {};
  const dep = rec.d?.[rec.d.length - 1] ?? null;
  const cat = CAT[category(dep)];
  const imd = check?.districts[id];
  const flagged = !!imd?.flag; // gridded estimate 2+ categories from IMD's own figure: lead with IMD's number
  const seasons = series?.season_dep || {};
  const ranked = Object.entries(seasons).filter(([, v]) => v != null).sort((a, b) => a[1] - b[1]);
  const rank = ranked.findIndex(([y]) => y === "2026") + 1;
  const rankText = rank && ranked.length > 1
    ? (rank === 1 ? `the driest of the last ${ranked.length} seasons` : rank === ranked.length ? `the wettest of the last ${ranked.length} seasons` : `${ordinal(rank)} driest of the last ${ranked.length} seasons`)
    : "";

  card.innerHTML = `
    <div class="card-head">
      <div><h3>${esc(label && !aliasNote ? label : p.name)}</h3><p class="card-state">${esc(p.state)}${label && !aliasNote && label.toLowerCase() !== p.name.toLowerCase() ? ` · shown as “${esc(p.name)}” on the 2021 map` : ""}</p>
        ${aliasNote ? `<p class="note">${esc(aliasNote)}. Its rainfall is part of ${esc(p.name)} on this map.</p>` : ""}</div>
      <div class="card-stat">
        ${flagged
          ? `<p class="dep" style="color:${imd.imd < 0 ? tok("--dry") : tok("--rain")}">${fmtPct(imd.imd)}</p>
             <p><span class="chip"><i style="${swatch(category(imd.imd))}"></i>${CAT[category(imd.imd)].label}</span> IMD, 1 Jun – ${fmtDate(check.period.slice(-10))}</p>`
          : `<p class="dep" style="color:${dep != null && dep < 0 ? tok("--dry") : tok("--rain")}">${fmtPct(dep)}</p>
             <p><span class="chip"><i style="${swatch(cat.key)}"></i>${cat.label}</span></p>`}
        ${imdLine(check, id)}
        <p>${rec.a != null ? `${fmtMm(rec.a)} fell, against ${fmtMm(rec.n)} normally` : "No complete 2026 data"}${rankText ? `.<br>2026 was ${rankText}.` : ""}</p>
      </div>
    </div>
    <div class="card-grid">
      <div>
        <p class="chart-title">Rain since 1 June, week by week (mm)</p>
        <div class="legend-inline">
          <span><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="${tok("--rain")}" stroke-width="3"/></svg>2026</span>
          <span><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="${tok("--ink")}" stroke-width="2" stroke-dasharray="5 3"/></svg>Normal (1971–2020)</span>
          <span><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="${tok("--past")}" stroke-width="1.5"/></svg>2021–2025</span>
        </div>
        <figure class="line-fig"><div id="line-chart"></div><div class="tip" id="line-tip" hidden></div></figure>
      </div>
      <div>
        <p class="chart-title">Whole-season departure, last six years</p>
        <p class="chart-sub">June–September rain against normal</p>
        <div id="years-chart"></div>
      </div>
    </div>
    <p class="note">District rainfall from IMD's 0.25° gridded daily data, averaged over the district (see Method). IMD's own district figures use rain-gauge averages and can differ by a few points.</p>`;
  if (series) {
    lineChart(document.getElementById("line-chart"), series, weeks);
    yearsChart(document.getElementById("years-chart"), seasons);
  }
}

function imdLine(check, id) {
  const c = check?.districts[id];
  if (!c) return "";
  const to = fmtDate(check.period.slice(-10));
  return c.flag
    ? `<p class="warn">⚠ Few rain gauges fed the gridded data here, so this site’s own estimate (${fmtPct(c.ours)}) is unreliable and the figure above is IMD’s station-based one. The charts below use the gridded data: read their shape, not their level.</p>`
    : `<p>IMD’s own figure to ${to}: ${fmtPct(c.imd)}</p>`;
}

function ordinal(n) { return n + (["th", "st", "nd", "rd"][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10] || "th"); }

function lineChart(el, s, weeks) {
  // drawn at the container's own width so text stays readable on phones
  const W = Math.max(300, Math.round(el.clientWidth || 640)), H = Math.round(Math.min(340, Math.max(240, W * 0.55))), m = { t: 12, r: 64, b: 30, l: 50 };
  const x = d3.scaleUtc().domain([new Date("2026-06-01"), new Date(weeks[weeks.length - 1])]).range([m.l, W - m.r]);
  const X = (i) => x(new Date(weeks[i]));
  const all = [s.normal, s["2026"], ...YEARS.map((y) => s[y])].flat().filter((v) => v != null);
  const y = d3.scaleLinear().domain([0, d3.max(all) * 1.06 || 1]).nice().range([H - m.b, m.t]);
  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
    .attr("aria-label", "Line chart of cumulative rainfall in 2026, the normal, and 2021 to 2025");
  svg.append("g").attr("class", "grid").attr("transform", `translate(${m.l},0)`)
    .call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat("")).call((g) => g.select(".domain").remove());
  svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`)
    .call(d3.axisLeft(y).ticks(5).tickFormat((v) => `${d3.format(",")(v)}`).tickSize(0).tickPadding(6)).call((g) => g.select(".domain").remove());
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
    .call(d3.axisBottom(x).ticks(d3.utcMonth.every(1)).tickFormat(d3.utcFormat("%b")).tickSizeOuter(0));
  const line = (arr) => d3.line().defined((v) => v != null).x((_, i) => X(i)).y((v) => y(v)).curve(d3.curveMonotoneX)(arr);
  const past = svg.append("g").selectAll("path").data(YEARS).join("path")
    .attr("d", (yr) => line(s[yr] || [])).attr("fill", "none").attr("stroke", tok("--past")).attr("stroke-width", 1.5);
  svg.append("path").attr("d", line(s.normal)).attr("fill", "none").attr("stroke", tok("--ink")).attr("stroke-width", 2).attr("stroke-dasharray", "6 4");
  svg.append("path").attr("d", line(s["2026"])).attr("fill", "none").attr("stroke", tok("--rain")).attr("stroke-width", 3).attr("stroke-linecap", "round");
  // end labels (direct labels for the two lines that matter)
  const last = weeks.length - 1;
  const ends = [{ v: s["2026"][last], t: "2026", c: "lbl-strong" }, { v: s.normal[last], t: "Normal", c: "lbl" }].filter((e) => e.v != null);
  if (ends.length === 2 && Math.abs(y(ends[0].v) - y(ends[1].v)) < 16) {
    const up = ends[0].v >= ends[1].v ? 0 : 1; ends[up].dy = -8; ends[1 - up].dy = 8;
  }
  svg.append("g").selectAll("text").data(ends).join("text").attr("class", (e) => `${e.c} halo`)
    .attr("x", X(last) + 6).attr("y", (e) => y(e.v) + (e.dy || 0)).attr("dy", "0.32em").text((e) => e.t);

  // crosshair + tooltip
  const fig = el.parentElement, tip = fig.querySelector(".tip");
  const cross = svg.append("line").attr("y1", m.t).attr("y2", H - m.b).attr("stroke", tok("--ink-2")).attr("stroke-width", 1).attr("visibility", "hidden");
  const dot = svg.append("circle").attr("r", 5).attr("fill", tok("--rain")).attr("stroke", "#fffdf8").attr("stroke-width", 2).attr("visibility", "hidden");
  svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b).attr("fill", "transparent")
    .on("pointermove", (e) => {
      const [mx] = d3.pointer(e);
      const i = d3.leastIndex(weeks, (w) => Math.abs(x(new Date(w)) - mx));
      cross.attr("x1", X(i)).attr("x2", X(i)).attr("visibility", "visible");
      if (s["2026"][i] != null) dot.attr("cx", X(i)).attr("cy", y(s["2026"][i])).attr("visibility", "visible");
      past.attr("stroke-width", 1.5);
      const rows = [["2026", s["2026"][i], true], ["Normal", s.normal[i]], ...YEARS.slice().reverse().map((yr) => [yr, s[yr]?.[i]])];
      tip.innerHTML = `<b>1 Jun – ${fmtDate(weeks[i])}</b><br>` + rows.map(([k, v, b]) => `${b ? "<b>" : ""}${k}: ${fmtMm(v)}${b ? "</b>" : ""}`).join("<br>");
      placeTip(tip, fig, e);
    })
    .on("pointerleave", () => { cross.attr("visibility", "hidden"); dot.attr("visibility", "hidden"); tip.hidden = true; });
}

function yearsChart(el, seasons) {
  const years = [...YEARS, "2026"];
  const vals = years.map((y) => seasons[y]);
  const W = Math.max(280, Math.round(el.clientWidth || 360)), rowH = 34, m = { t: 6, r: 52, b: 6, l: 46 }, H = m.t + m.b + rowH * years.length;
  const ext = Math.max(40, d3.max(vals, (v) => Math.abs(v ?? 0)) * 1.1);
  const x = d3.scaleLinear().domain([-ext, ext]).range([m.l, W - m.r]);
  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
    .attr("aria-label", `Season rainfall departure: ${years.map((y, i) => `${y} ${fmtPct(vals[i])}`).join(", ")}`);
  svg.append("line").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t).attr("y2", H - m.b).attr("stroke", tok("--ink")).attr("stroke-width", 1);
  for (const b of [-20, 20]) svg.append("line").attr("x1", x(b)).attr("x2", x(b)).attr("y1", m.t).attr("y2", H - m.b).attr("stroke", tok("--rule")).attr("stroke-dasharray", "3 3");
  const row = svg.append("g").selectAll("g").data(years).join("g").attr("transform", (_, i) => `translate(0,${m.t + i * rowH})`);
  row.append("text").attr("class", (y) => (y === "2026" ? "lbl-strong" : "lbl")).attr("x", 0).attr("y", rowH / 2).attr("dy", "0.32em").text((y) => y);
  row.append("path").attr("d", (y) => {
    const v = seasons[y]; if (v == null) return null;
    const x0 = x(0), x1 = x(v), h = 14, r = Math.min(4, Math.abs(x1 - x0)), top = rowH / 2 - h / 2, dir = v >= 0 ? 1 : -1;
    // flat at the baseline, rounded at the data end
    return `M${x0},${top}H${x1 - dir * r}q${dir * r},0 ${dir * r},${r}V${top + h - r}q0,${r} ${-dir * r},${r}H${x0}Z`;
  }).attr("fill", (y) => { const c = CAT[category(seasons[y])]; return c.key === "NR" ? c.color : c.color; })
    .attr("stroke", (y) => (category(seasons[y]) === "N" ? tok("--past") : "none")).attr("stroke-width", 1);
  row.append("text").attr("class", (y) => (y === "2026" ? "lbl-strong" : "lbl"))
    .attr("x", (y) => (seasons[y] == null ? x(0) + 6 : seasons[y] >= 0 ? x(seasons[y]) + 6 : x(seasons[y]) - 6))
    .attr("text-anchor", (y) => (seasons[y] != null && seasons[y] < 0 ? "end" : "start"))
    .attr("y", rowH / 2).attr("dy", "0.32em").text((y) => fmtPct(seasons[y]));
  d3.select(el).append("p").attr("class", "note").style("margin", "4px 0 0").text("Dashed lines mark ±20%, IMD's edge of “normal”.");
}

export function initDistrict({ districts, aliases, weekly, map, check }) {
  const { idx, byId } = buildIndex(districts, aliases);
  let last = null;
  const pick = (id, note = null, label = null) => {
    last = [id, note, label];
    showDistrict(id, { byId, weekly, aliasNote: note, label, check });
    map.focus(id);
    history.replaceState(null, "", `#d=${id}`);
  };
  initSearch(idx, (it) => {
    pick(it.id, it.note ? `${it.label} is a newer district (${it.note.replace(/; not in.*$/, "")})` : null, it.label);
    document.getElementById("district").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  bus.addEventListener("select", (e) => { pick(e.detail); document.getElementById("district").scrollIntoView({ behavior: "smooth" }); });
  // charts are drawn at their container's width: redraw when that changes (rotation, resize)
  let width = innerWidth;
  addEventListener("resize", () => {
    if (Math.abs(innerWidth - width) < 40 || !last) return;
    width = innerWidth;
    clearTimeout(pick.t);
    pick.t = setTimeout(() => showDistrict(last[0], { byId, weekly, aliasNote: last[1], label: last[2], check }), 200);
  });
  const fromHash = decodeURIComponent((location.hash.match(/^#d=(.+)$/) || [])[1] || "");
  addEventListener("hashchange", () => {
    const id = decodeURIComponent((location.hash.match(/^#d=(.+)$/) || [])[1] || "");
    if (byId[id] && id !== last?.[0]) { pick(id); document.getElementById("district").scrollIntoView(); }
  });
  pick(byId[fromHash] ? fromHash : "maharashtra--pune");
  if (byId[fromHash]) document.getElementById("district").scrollIntoView();
}
