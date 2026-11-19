// Section 5: state rainfall departure vs change in kharif sown area (PIB, area as on 4 Sep 2026).
import { CAT, category, esc, fmtDate, fmtPct, placeTip, tok } from "./common.js";

const CROPS = ["Rice", "Pulses", "Coarse cereals", "Oilseeds", "Cotton"];
const PIB_TO_MAP = { "Jammu & Kashmir": "Jammu and Kashmir" };

export function initSowing({ sowing, states, weekly }) {
  const rel = sowing.releases[sowing.latest];
  // rainfall up to the IMD week that ends just before the sowing date
  const wk = weekly.weeks.reduce((best, w, i) => (w <= sowing.latest ? i : best), 0);
  const asOf = weekly.weeks[wk];
  const rows = Object.entries(rel.states).map(([name, crops]) => {
    const st = states[PIB_TO_MAP[name] || name];
    return { name, crops, dep: st ? st.weekly_dep[wk] : null };
  });
  const tabs = document.getElementById("crop-tabs");
  tabs.innerHTML = CROPS.map((c, i) => `<button role="tab" type="button" aria-selected="${i === 0}" data-crop="${c}">${c}</button>`).join("");
  tabs.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    tabs.querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    draw(b.dataset.crop);
  });

  const t = rel.totals;
  document.getElementById("sowing-lede").innerHTML =
    `By ${fmtDate(sowing.latest)}, farmers had sown <b>${d3.format(",.1f")(t.Total.this_year)} lakh hectares</b> of kharif crops, ` +
    `${d3.format(",.1f")(Math.abs(t.Total.change))} lakh ha ${t.Total.change < 0 ? "less" : "more"} than at the same point last year. ` +
    `Rice fell most (${d3.format("+,.2f")(t.Rice.change)} lakh ha). Each dot is a state the Agriculture Ministry named as a major rise or fall for that crop, placed by how much rain it had had.`;

  const fig = document.querySelector(".sowing-figure"), tip = document.getElementById("sowing-tip");
  let current = "Rice", width = innerWidth;
  addEventListener("resize", () => {
    if (Math.abs(innerWidth - width) < 40) return;
    width = innerWidth; clearTimeout(draw.t); draw.t = setTimeout(() => draw(current), 200);
  });
  function draw(crop) {
    current = crop;
    const data = rows.filter((r) => r.crops[crop] != null && r.dep != null);
    const el = document.getElementById("sowing-chart"); el.innerHTML = "";
    const W = Math.max(320, Math.round(el.clientWidth || 760)), H = Math.round(Math.max(360, Math.min(460, W * 0.6))), m = { t: 26, r: 16, b: 50, l: 52 };
    const xe = Math.max(30, d3.max(rows, (r) => Math.abs(r.dep ?? 0)) * 1.1);
    const ye = Math.max(1, d3.max(data, (r) => Math.abs(r.crops[crop])) * 1.2);
    const x = d3.scaleLinear().domain([-xe, xe]).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([-ye, ye]).range([H - m.b, m.t]).nice();
    const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
      .attr("aria-label", `Scatter of ${data.length} states: rainfall departure against change in ${crop} area`);
    // quadrant hints
    svg.append("rect").attr("x", m.l).attr("y", y(0)).attr("width", x(0) - m.l).attr("height", H - m.b - y(0)).attr("fill", tok("--c-d")).attr("opacity", 0.08);
    svg.append("g").attr("class", "grid").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(6).tickSize(-(W - m.l - m.r)).tickFormat("")).call((g) => g.select(".domain").remove());
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(6).tickFormat(d3.format("+.1~f")).tickSize(0).tickPadding(6)).call((g) => g.select(".domain").remove());
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(6).tickFormat((v) => fmtPct(v)).tickSizeOuter(0));
    svg.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y(0)).attr("y2", y(0)).attr("stroke", tok("--ink")).attr("stroke-width", 1);
    svg.append("line").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t).attr("y2", H - m.b).attr("stroke", tok("--ink")).attr("stroke-width", 1);
    svg.append("text").attr("class", "lbl").attr("x", m.l + 6).attr("y", H - m.b - 8).text("Drier, and sowed less");
    svg.append("text").attr("class", "lbl").attr("x", (m.l + W - m.r) / 2).attr("y", H - 8).attr("text-anchor", "middle").text(`Rainfall against normal, 1 Jun – ${fmtDate(asOf)}`);
    svg.append("text").attr("class", "lbl").attr("x", 4).attr("y", 12).text(`Change in ${crop.toLowerCase()} area vs last year (lakh ha)`);
    const g = svg.append("g").selectAll("g").data(data).join("g").attr("transform", (r) => `translate(${x(r.dep)},${y(r.crops[crop])})`);
    g.append("circle").attr("r", 8).attr("fill", (r) => CAT[category(r.dep)].color).attr("stroke", tok("--ink")).attr("stroke-width", 1);
    g.append("circle").attr("r", 18).attr("fill", "transparent")
      .on("pointermove", (e, r) => {
        tip.innerHTML = `<b>${esc(r.name)}</b><br>Rain ${fmtPct(r.dep)} (to ${fmtDate(asOf)})<br>${crop}: ${d3.format("+.2f")(r.crops[crop])} lakh ha vs last year`;
        placeTip(tip, fig, e);
      }).on("pointerleave", () => { tip.hidden = true; });
    // labels: right of the dot (left near the right edge), nudged apart vertically where they would overlap
    const labs = data.map((r) => {
      const left = x(r.dep) > W - 160;
      const w = r.name.length * 7.6 + 4;
      const x0 = left ? x(r.dep) - 12 - w : x(r.dep) + 12;
      return { r, left, x0, x1: x0 + w, y: y(r.crops[crop]), y0: y(r.crops[crop]) };
    }).sort((a, b) => a.y - b.y);
    for (let pass = 0; pass < 6; pass++) {
      for (let i = 0; i < labs.length; i++) for (let j = i + 1; j < labs.length; j++) {
        const a = labs[i], b = labs[j];
        if (a.x1 < b.x0 || b.x1 < a.x0) continue;
        const gap = 16 - (b.y - a.y);
        if (gap > 0) { a.y -= gap / 2; b.y += gap / 2; }
      }
    }
    const lab = svg.append("g").selectAll("g").data(labs).join("g");
    lab.filter((l) => Math.abs(l.y - l.y0) > 5).append("line")
      .attr("x1", (l) => x(l.r.dep) + (l.left ? -8 : 8)).attr("y1", (l) => l.y0)
      .attr("x2", (l) => (l.left ? l.x1 : l.x0) - (l.left ? -2 : 2)).attr("y2", (l) => l.y)
      .attr("stroke", tok("--past")).attr("stroke-width", 1);
    lab.append("text").attr("class", "lbl-strong halo").attr("x", (l) => (l.left ? l.x1 : l.x0)).attr("y", (l) => l.y)
      .attr("text-anchor", (l) => (l.left ? "end" : "start")).attr("dy", "0.32em").text((l) => l.r.name);
    const missing = rows.filter((r) => r.crops[crop] != null && r.dep == null).map((r) => r.name);
    const tot = t[crop];
    document.getElementById("sowing-caption").innerHTML =
      `${data.length} states named for ${crop.toLowerCase()} in the release; other states’ changes were not published, so they are not shown (not zero).` +
      (tot ? ` All India: ${d3.format(",.2f")(tot.this_year)} lakh ha sown vs ${d3.format(",.2f")(tot.last_year)} last year.` : "") +
      (missing.length ? ` No rainfall match for: ${missing.map(esc).join(", ")}.` : "") +
      ` Dot colour = IMD rainfall category. Source: <a href="${rel.url}">PIB, area as on ${fmtDate(sowing.latest)}</a>.`;
  }
  draw("Rice");

  const order = ["Rice", "Pulses", "Coarse cereals", "Oilseeds", "Sugarcane", "Jute & mesta", "Cotton", "Total"];
  document.getElementById("sowing-table").innerHTML = `<div class="tablewrap"><table>
    <thead><tr><th>Crop</th><th>Normal area</th><th>Sown, 2026</th><th>Same week, 2025</th><th>Change</th></tr></thead><tbody>
    ${order.filter((c) => t[c]).map((c) => `<tr><td>${c === "Total" ? "<b>All kharif crops</b>" : c}</td><td>${t[c].normal.toFixed(2)}</td><td>${t[c].this_year.toFixed(2)}</td><td>${t[c].last_year.toFixed(2)}</td><td>${d3.format("+.2f")(t[c].change)}</td></tr>`).join("")}
    </tbody></table></div><p class="note">Lakh hectares, as on ${fmtDate(sowing.latest)}. Crops missing from this table could not be read from the release.</p>`;
}
