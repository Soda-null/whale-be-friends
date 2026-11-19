// The window into her cottage (decision 62): her room as it is right now, drawn from what
// `fish window` says. Everything is drawn here as shapes; the only picture is her face. Text from
// her room goes in as text (textContent), never as HTML.
"use strict";

const SVG = "http://www.w3.org/2000/svg";
const STILL = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let drawn = 0, ID = "w0-";  // each picture's own names for its gradients and clips
const ref = name => `url(#${ID}${name})`;

function s(tag, attrs, ...children) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) node.setAttribute(k, v);
  for (const c of children) if (c !== null && c !== undefined && c !== false) node.append(c);
  return node;
}
function words(x, y, text, attrs, ...more) { return s("text", { x, y, ...attrs }, String(text), ...more); }
function hint(text) { return s("title", {}, String(text)); }  // what a thing says when the mouse rests on it
function moving(attr, values, seconds, extra) {
  return STILL ? null : s("animate", { attributeName: attr, values, dur: `${seconds}s`, repeatCount: "indefinite", ...extra });
}
function drift(values, seconds, extra) {  // moves a thing along, "x y;x y"
  return STILL ? null : s("animateTransform", { attributeName: "transform", type: "translate", values, dur: `${seconds}s`,
    repeatCount: "indefinite", ...extra });
}

// Colours of the sky and of the land, by the light outside.
const LIGHT = {
  day:   { top: "#9fc2f4", low: "#e8f0fd", hill: "#9cb7d8", lake: ["#9cc0ee", "#6f98d6"], grass: "#9dc98a", far: "#b9d4a5" },
  dusk:  { top: "#5d5a9e", low: "#f6c49b", hill: "#8a7fb0", lake: ["#c3a7c9", "#7d79b0"], grass: "#7f9d74", far: "#98a986" },
  night: { top: "#0f1535", low: "#343c74", hill: "#252c58", lake: ["#2d3870", "#1b2250"], grass: "#2f4636", far: "#384d40" },
};
// Where she stands for each spot in the picture (the middle of her face).
const SPOT = {
  bed: [372, 438], stove: [758, 472], sink: [714, 472], sill: [372, 344], tank: [436, 344],
  desk: [574, 404], lake: [128, 418], shop: [912, 452], florist: [912, 452],
};
const AWAY_WORDS = { shop: "去菜店了", lake: "在湖边码头坐着", florist: "去花店了" };

function defs(light) {
  const c = LIGHT[light] || LIGHT.day;
  return s("defs", {},
    s("linearGradient", { id: ID + "sky", x1: 0, y1: 0, x2: 0, y2: 1 },
      s("stop", { offset: "0", "stop-color": c.top }), s("stop", { offset: "1", "stop-color": c.low })),
    s("linearGradient", { id: ID + "lake", x1: 0, y1: 0, x2: 0, y2: 1 },
      s("stop", { offset: "0", "stop-color": c.lake[0] }), s("stop", { offset: "1", "stop-color": c.lake[1] })),
    s("radialGradient", { id: ID + "lamp" },
      s("stop", { offset: "0", "stop-color": "#ffd98f", "stop-opacity": ".75" }),
      s("stop", { offset: "1", "stop-color": "#ffd98f", "stop-opacity": "0" })),
    s("radialGradient", { id: ID + "heat" },
      s("stop", { offset: "0", "stop-color": "#ff9a52", "stop-opacity": ".7" }),
      s("stop", { offset: "1", "stop-color": "#ff9a52", "stop-opacity": "0" })),
    s("clipPath", { id: ID + "face" }, s("circle", { cx: 0, cy: 0, r: 27 })),
    s("clipPath", { id: ID + "pane" }, s("rect", { x: 296, y: 248, width: 150, height: 122, rx: 4 })));
}

// --- outside -------------------------------------------------------------------------------

function sky(d) {
  const c = LIGHT[d.light] || LIGHT.day;
  const grey = ["overcast", "rain", "snow", "fog"].includes(d.sky);
  const g = s("g", {}, s("rect", { x: 0, y: 0, width: 1000, height: 600, fill: ref("sky") }));
  if (d.light === "night") {
    if (!grey) for (const [x, y, r] of [[90, 60, 1.6], [180, 120, 1.2], [640, 50, 1.4], [720, 140, 1], [940, 180, 1.3], [300, 40, 1.1], [860, 40, 1.5]])
      g.append(s("circle", { cx: x, cy: y, r, fill: "#fff8d8", opacity: .85 }, moving("opacity", ".85;.3;.85", 3 + x % 4)));
    if (!grey) g.append(s("path", { d: "M884 60 A26 26 0 1 0 884 112 A20 26 0 1 1 884 60 Z", fill: "#fff4c8" }));
  } else if (!grey) {
    const low = d.light === "dusk";
    g.append(s("circle", { cx: 880, cy: low ? 262 : 92, r: low ? 34 : 30, fill: low ? "#ffb26b" : "#ffe9a6" }));
  }
  if (d.sky === "cloudy" || grey) {
    const tone = d.light === "night" ? "#4b5389" : grey ? "#c9cfdd" : "#ffffff";
    for (const [x, y, k] of [[150, 90, 1], [520, 60, 1.3], [820, 120, 1.1], [360, 150, .8]])
      g.append(s("g", { opacity: grey ? .95 : .8, fill: tone },
        s("ellipse", { cx: x, cy: y, rx: 60 * k, ry: 20 * k }), s("ellipse", { cx: x + 25 * k, cy: y - 14 * k, rx: 34 * k, ry: 20 * k }),
        s("ellipse", { cx: x - 28 * k, cy: y - 8 * k, rx: 26 * k, ry: 15 * k }),
        drift(`0 0;${18 * k} 0;0 0`, 40 + x % 13)));
  }
  return g;
}

function land(d) {
  const c = LIGHT[d.light] || LIGHT.day;
  return s("g", {},
    s("path", { d: "M0 340 Q120 280 240 322 T470 312 T720 318 T1000 300 L1000 380 L0 380 Z", fill: c.hill }),
    s("rect", { x: 0, y: 368, width: 300, height: 232, fill: ref("lake") },
      hint("湖")),
    ...[392, 430, 470].map((y, i) => s("path", { d: `M${30 + i * 40} ${y} h70`, stroke: "#ffffff", "stroke-opacity": ".35", "stroke-width": 2, "stroke-linecap": "round" },
      moving("stroke-opacity", ".35;.08;.35", 4 + i))),
    // the little pier
    s("g", { fill: "#a77a4c" }, s("rect", { x: 40, y: 442, width: 170, height: 12, rx: 2 }),
      ...[52, 100, 148, 196].map(x => s("rect", { x, y: 452, width: 6, height: 36, fill: "#7c5733" })), hint("湖边小码头")),
    s("path", { d: "M300 520 Q260 470 300 380 L1000 380 L1000 600 L300 600 Z", fill: c.far }),
    s("rect", { x: 0, y: 540, width: 1000, height: 60, fill: c.grass }),
    // the way to town
    s("path", { d: "M808 540 Q880 500 1000 492 L1000 520 Q890 528 840 560 Z", fill: "#e4d2ae", opacity: .9 }),
    s("g", {}, s("rect", { x: 930, y: 446, width: 6, height: 50, fill: "#7c5733" }),
      s("rect", { x: 900, y: 440, width: 70, height: 22, rx: 4, fill: "#f6e7c8", stroke: "#7c5733" }),
      words(935, 456, "镇上 →", { "font-size": 12, "text-anchor": "middle", fill: "#5b4128", "dominant-baseline": "middle" }),
      hint("往镇上走：菜店十分钟，花店十五分钟")));
}

function weather(d) {
  const g = s("g", { "pointer-events": "none" });
  if (d.sky === "rain") {
    for (let i = 0; i < 70; i++) {
      const x = (i * 137) % 1000, y = (i * 61) % 560;
      g.append(s("path", { d: `M${x} ${y} l-6 16`, stroke: "#dfe8f8", "stroke-width": 1.4, opacity: .7 },
        drift("0 -40;-14 600", 0.9 + (i % 5) / 10, { begin: `-${(i % 9) / 10}s` })));
    }
  } else if (d.sky === "snow") {
    for (let i = 0; i < 60; i++) {
      const x = (i * 149) % 1000, y = (i * 53) % 560;
      g.append(s("circle", { cx: x, cy: y, r: 2 + (i % 3), fill: "#ffffff", opacity: .85 },
        drift(`0 -60;${(i % 7) - 3} 620`, 6 + (i % 4), { begin: `-${i % 6}s` })));
    }
  } else if (d.sky === "fog") {
    g.append(s("rect", { x: 0, y: 260, width: 1000, height: 300, fill: "#eef1f6", opacity: .45 }));
  }
  return g;
}

// --- the house -----------------------------------------------------------------------------

function house(d) {
  const lit = d.light !== "day" && !(d.her.asleep && d.light === "night");
  const wall = d.light === "night" ? (lit ? "#e7c995" : "#8f7a63") : d.light === "dusk" ? "#efd3a6" : "#f3e0bd";
  return s("g", {},
    // the window and what it looks out on, then the walls around it
    s("g", { "clip-path": ref("pane") }, s("rect", { x: 296, y: 248, width: 150, height: 122, fill: ref("sky") }),
      s("rect", { x: 296, y: 330, width: 150, height: 40, fill: ref("lake") })),
    s("path", { fill: wall, "fill-rule": "evenodd",
      d: "M268 222 L800 222 L800 540 L268 540 Z M296 248 h150 v122 h-150 Z" }),
    lit ? s("circle", { cx: 560, cy: 300, r: 230, fill: ref("lamp") }) : null,
    s("path", { d: "M296 248 h150 v122 h-150 Z M371 248 v122 M296 309 h150", fill: "none", stroke: "#8a6440", "stroke-width": 5 }),
    s("path", { d: "M300 250 q20 40 4 118 l-8 0 Z", fill: "#ffffff", opacity: .8 }),
    s("path", { d: "M442 250 q-20 40 -4 118 l8 0 Z", fill: "#ffffff", opacity: .8 }),
    // the roof, the floor, the frame
    s("path", { d: "M236 230 L534 92 L832 230 L806 238 L534 116 L262 238 Z", fill: "#7d5b47" }),
    s("rect", { x: 512, y: 70, width: 30, height: 50, fill: "#8b8b95" }),
    s("rect", { x: 268, y: 500, width: 532, height: 40, fill: "#c89560" }),
    s("path", { d: "M268 222 V540 M800 222 V540 M268 540 H800", stroke: "#6b4a2f", "stroke-width": 9, fill: "none" }),
    s("path", { d: "M300 520 h460", stroke: "#b07f4f", "stroke-width": 2 }),
    // the lamp under the roof
    s("path", { d: "M560 170 V214", stroke: "#5b4128", "stroke-width": 2 }),
    s("path", { d: "M545 214 h30 l-6 18 h-18 Z", fill: lit ? "#ffd27a" : "#a58b6a", stroke: "#5b4128" }),
    // the shelf with her books, the desk, the chair
    s("g", {}, s("rect", { x: 520, y: 262, width: 86, height: 8, fill: "#a77a4c" }),
      ...["#7f95e6", "#e2a457", "#9dc98a", "#e98b7a", "#c3b5e8"].map((f, i) => s("rect", { x: 526 + i * 15, y: 236 + (i % 2) * 4, width: 11, height: 26 - (i % 2) * 4, fill: f })),
      hint("书架")),
    s("rect", { x: 520, y: 438, width: 104, height: 10, rx: 2, fill: "#a77a4c" }),
    s("rect", { x: 526, y: 448, width: 7, height: 52, fill: "#8a6440" }), s("rect", { x: 611, y: 448, width: 7, height: 52, fill: "#8a6440" }),
    s("rect", { x: 540, y: 418, width: 36, height: 20, rx: 2, fill: "#5a6a92" }),
    s("rect", { x: 590, y: 424, width: 12, height: 14, rx: 2, fill: "#ffffff" }),
    s("path", { d: "M632 438 v62 M660 438 v62 M628 470 h36", stroke: "#8a6440", "stroke-width": 5 }),
    // the thermometer on the wall
    s("g", {}, s("rect", { x: 478, y: 252, width: 46, height: 26, rx: 6, fill: "#fffaf0", stroke: "#b07f4f" }),
      words(501, 266, `${d.temp}°`, { "font-size": 15, "text-anchor": "middle", "dominant-baseline": "middle",
        fill: d.temp < 16 ? "#3f62c9" : d.temp >= 29 ? "#c8502b" : "#5b4128", "font-weight": 600 }),
      hint(d.words.warmth + (d.outside !== null && d.outside !== undefined ? `；外面 ${Math.round(d.outside)} 度` : ""))));
}

function bed(d) {
  const asleep = d.bed === "在睡" || (d.her.asleep && d.her.spot === "bed");
  const messy = d.bed === "乱";
  return s("g", {},
    s("rect", { x: 284, y: 470, width: 172, height: 30, rx: 4, fill: "#b98a5b" }),
    s("rect", { x: 288, y: 452, width: 164, height: 24, rx: 8, fill: "#fffaf0" }),
    s("ellipse", { cx: 312, cy: 450, rx: 20, ry: 10, fill: "#ffffff", stroke: "#e6dcc8" }),
    s("ellipse", { cx: 330, cy: 444, rx: 14, ry: 9, fill: "#a9bdf0" }),  // the whale plush
    asleep ? s("path", { d: "M318 452 q60 -26 132 -6 v22 h-132 Z", fill: "#a9bdf0" })
      : messy ? s("path", { d: "M350 452 q20 -10 40 2 q18 -12 36 0 q14 -6 24 4 v18 h-100 Z", fill: "#a9bdf0" })
        : s("rect", { x: 402, y: 446, width: 46, height: 22, rx: 5, fill: "#a9bdf0" }),
    s("rect", { x: 284, y: 470, width: 172, height: 30, rx: 4, fill: "transparent" }, hint(d.words.bed)));
}

function heater(d) {
  return s("g", {},
    d.heater ? s("circle", { cx: 478, cy: 478, r: 46, fill: ref("heat") },
      moving("r", "42;50;42", 2.4)) : null,
    s("rect", { x: 464, y: 456, width: 28, height: 44, rx: 5, fill: "#e9e4dc", stroke: "#9c8e7c" }),
    ...[464, 472, 480, 488].map(y => s("path", { d: `M469 ${y} h18`, stroke: d.heater ? "#ff7a3a" : "#b9ae9f", "stroke-width": 2.4 })),
    s("rect", { x: 464, y: 456, width: 28, height: 44, fill: "transparent" }, hint(d.heater ? "取暖器开着" : "取暖器关着")));
}

function kitchen(d) {
  const meals = d.fridge.reduce((n, f) => n + f.meals, 0);
  const fridgeWords = d.fridge.length ? "冰箱里有" + d.fridge.map(f => `${f.name}（够 ${f.meals} 顿）`).join("、") : "冰箱空了";
  const g = s("g", {},
    // the fridge, a dot for each meal in it
    s("rect", { x: 646, y: 360, width: 58, height: 140, rx: 6, fill: "#f5f7fc", stroke: "#b9c1d6" }),
    s("path", { d: "M646 404 h58 M694 372 v20 M694 414 v30", stroke: "#b9c1d6", "stroke-width": 2 }),
    ...Array.from({ length: Math.min(meals, 12) }, (_, i) => s("circle", { cx: 658 + (i % 4) * 11, cy: 422 + Math.floor(i / 4) * 11, r: 3.6,
      fill: ["#f2c14e", "#7fbf6a", "#e98b7a", "#c99560"][i % 4] })),
    s("rect", { x: 646, y: 360, width: 58, height: 140, fill: "transparent" }, hint(fridgeWords)),
    // the counter, the sink and what is waiting in it, the stove
    s("rect", { x: 708, y: 444, width: 88, height: 56, fill: "#c9a77d" }),
    s("rect", { x: 704, y: 438, width: 96, height: 8, rx: 2, fill: "#efe7da" }),
    s("rect", { x: 714, y: 432, width: 36, height: 8, rx: 3, fill: "#9fb1c8" }),
    s("path", { d: "M740 432 v-16 h-10", stroke: "#9c9fa8", "stroke-width": 3, fill: "none" }));
  for (let i = 0; i < Math.min(d.sink, 6); i++)
    g.append(s("ellipse", { cx: 732 - (i % 2) * 4, cy: 428 - i * 5, rx: 13, ry: 4, fill: "#ffffff", stroke: "#c4cad8" }));
  g.append(s("rect", { x: 712, y: 400, width: 40, height: 44, fill: "transparent" }, hint(d.sink ? `水槽里有 ${d.sink} 样没洗` : "水槽是干净的")));
  g.append(s("rect", { x: 758, y: 432, width: 34, height: 6, rx: 2, fill: "#3c3f4a" }),
    s("path", { d: "M762 432 v-14 h26 v14", fill: d.cooking ? "#b6bcc9" : "#c7ccd6", stroke: "#7c8291" }),
    s("rect", { x: 758, y: 414, width: 34, height: 24, fill: "transparent" }, hint(d.cooking ? `在${d.her.doing}` : "灶台")));
  if (d.cooking) for (const [x, delay] of [[768, 0], [776, .7], [784, 1.4]])
    g.append(s("path", { d: `M${x} 412 q-5 -8 0 -16 q5 -8 0 -16`, stroke: "#ffffff", "stroke-width": 3, fill: "none", "stroke-linecap": "round", opacity: .8 },
      moving("opacity", "0;.85;0", 2.1, { begin: `${delay}s` })));
  // the rice jar, filled to how many meals are left
  const full = d.rice_full || 12, h = Math.round(30 * Math.min(d.rice, full) / full);
  g.append(s("rect", { x: 770, y: 342, width: 22, height: 34, rx: 6, fill: "#fdfaf3", stroke: "#b9a88c" }),
    s("rect", { x: 772, y: 374 - h, width: 18, height: h, rx: 4, fill: "#f4ecd9" }),
    s("rect", { x: 766, y: 376, width: 30, height: 5, fill: "#a77a4c" }),
    s("rect", { x: 770, y: 342, width: 22, height: 34, fill: "transparent" }, hint(`米缸${d.rice_word}`)));
  return g;
}

function plant(p, x) {
  const g = s("g", {});
  g.append(s("path", { d: `M${x - 14} 362 h28 l-4 18 h-20 Z`, fill: "#c8714a" }));
  if (!p) return g.append(hint("空花盆")), g;
  const droop = p.wilted ? 0.55 : 1;
  const tall = (6 + 10 * p.stage) * droop;
  const green = p.wilted ? "#a8a36a" : "#5e9e4e";
  if (p.stage === 0) g.append(s("path", { d: `M${x - 10} 362 h20`, stroke: "#7a5634", "stroke-width": 3 }));
  else if (p.plant === "小葱") for (const dx of [-6, 0, 6]) g.append(s("path", { d: `M${x + dx} 362 q${dx / 2} ${-tall / 2} ${dx} ${-tall}`, stroke: green, "stroke-width": 3, fill: "none", "stroke-linecap": "round" }));
  else {
    g.append(s("path", { d: `M${x} 362 v${-tall}`, stroke: green, "stroke-width": 2.4 }));
    for (let i = 0; i < Math.max(1, p.stage); i++) {
      const y = 362 - tall * (i + 1) / (p.stage + 1);
      g.append(s("ellipse", { cx: x + (i % 2 ? 7 : -7), cy: y, rx: 7, ry: 3.6 * droop + 1, fill: green, transform: `rotate(${i % 2 ? -25 : 25} ${x} ${y})` }));
    }
    for (let i = 0; i < Math.min(p.ready, 4); i++)
      g.append(s("circle", { cx: x - 6 + i * 4, cy: 362 - tall * .55 + (i % 2) * 5, r: 3.4, fill: p.plant === "小番茄" ? "#e0483a" : "#8cc26a" }));
  }
  const how = p.wilted ? "蔫了" : p.ready ? "能摘了" : p.stage === 0 ? "还没出芽" : `长到第 ${p.stage} 步了`;
  g.append(s("rect", { x: x - 16, y: 362 - tall - 6, width: 32, height: tall + 24, fill: "transparent" },
    hint(`${p.plant}：${how}` + (p.dry >= 2 ? `，${p.dry} 天没浇水了` : ""))));
  return g;
}

function sill(d) {
  const g = s("g", {}, s("rect", { x: 284, y: 378, width: 176, height: 10, rx: 2, fill: "#d9a86a" }));
  d.pots.forEach((p, i) => g.append(plant(p, 312 + i * 40)));
  d.flowers.slice(0, 3).forEach((f, i) => {
    const x = 392 + i * 13;
    g.append(s("g", {}, s("rect", { x: x - 5, y: 368, width: 10, height: 10, rx: 2, fill: "#e8b48a" }),
      s("path", { d: `M${x} 368 v-${f.wilted ? 6 : 12}`, stroke: "#5e9e4e", "stroke-width": 2 }),
      s("circle", { cx: x, cy: f.wilted ? 361 : 355, r: 4.5, fill: f.wilted ? "#c7b38a" : ["#f2c14e", "#e98bb4", "#ffffff"][i % 3] }),
      hint(`${f.name}${f.wilted ? "（蔫了）" : ""}`)));
  });
  if (d.sill.length) g.append(s("g", {}, s("rect", { x: 300, y: 386, width: 16, height: 6, fill: "#fff3c4", stroke: "#d6b765" }),
    hint("窗台上还放着：" + d.sill.join("、"))));
  if (d.tank) {
    const t = d.tank;
    const water = ["#bfe3f6", "#cfd8b8", "#b0b48c"][t.cloudy];
    const fishY = t.sad ? 372 : 360;
    g.append(s("g", {},
      s("rect", { x: 418, y: 342, width: 40, height: 36, rx: 3, fill: water, opacity: .9, stroke: "#9bb3c9" }),
      s("path", { d: "M422 376 q6 -12 3 -22 M450 376 q-4 -10 0 -18", stroke: "#5e9e4e", "stroke-width": 2, fill: "none" }),
      s("g", {}, s("ellipse", { cx: 438, cy: fishY, rx: 7, ry: 4, fill: "#f08a32" }), s("path", { d: `M445 ${fishY} l6 -4 v8 Z`, fill: "#f08a32" }),
        t.sad ? null : drift("-6 0;6 1;-6 0", 7)),
      hint(d.words.tank || "鱼缸")));
  }
  return g;
}

// --- who is there --------------------------------------------------------------------------

function bubble(x, y, text, below) {
  const w = Math.max(56, [...text].reduce((n, ch) => n + (ch.charCodeAt(0) > 255 ? 13 : 7), 0) + 18);
  const left = Math.min(Math.max(x - w / 2, 8), 992 - w);
  const top = below ? y + 8 : y - 30;  // y: the top of her head, or (below) her chin
  return s("g", {},
    s("rect", { x: left, y: top, width: w, height: 26, rx: 13, fill: "#fffdf8", stroke: "#d9cdb8" }),
    s("path", { d: below ? `M${x - 6} ${top + 1} l6 -8 l6 8 Z` : `M${x - 6} ${y - 5} l6 8 l6 -8 Z`, fill: "#fffdf8" }),
    words(left + w / 2, top + 14, text, { "font-size": 13, "text-anchor": "middle", "dominant-baseline": "middle", fill: "#27325c" }));
}
const UNDER = new Set(["stove", "sink"]);

function her(d) {
  const spot = d.her.out ? d.her.out : d.her.spot;
  const [x, y] = SPOT[spot] || SPOT.desk;
  const asleep = d.her.asleep;
  const doing = d.her.out ? AWAY_WORDS[d.her.out] || d.her.doing : asleep ? "睡着了" : d.her.doing;
  const g = s("g", {});
  const face = s("g", { transform: `translate(${x} ${y})${asleep ? " rotate(-70)" : ""}` },
    s("circle", { cx: 0, cy: 0, r: 30, fill: "#ffffff" }),
    s("image", { href: "/img/her.webp", x: -27, y: -27, width: 54, height: 54, "clip-path": ref("face"), preserveAspectRatio: "xMidYMid slice",
      opacity: asleep ? .9 : 1 }),
    asleep ? null : drift("0 0;0 -3;0 0", 3.2, { additive: "sum" }));
  g.append(face);
  if (asleep) for (const [dx, dy, k] of [[26, -26, 1], [38, -42, 1.3], [52, -60, 1.6]])
    g.append(words(x + dx, y + dy, "z", { "font-size": 12 * k, fill: "#7f95e6", "font-weight": 700 }, moving("opacity", "0;1;0", 3, { begin: `${dx / 40}s` })));
  const said = doing + (d.her.until ? ` · 到 ${d.her.until}` : "");
  if (!asleep) g.append(UNDER.has(spot) ? bubble(x, y + 30, said, true) : bubble(x, y - 32, said));  // asleep: the z's say it
  g.append(s("circle", { cx: x, cy: y, r: 30, fill: "transparent" }, hint(d.mood ? `她：${d.mood}` : "她")));
  return g;
}

function him(d) {
  if (d.guest !== "here") return null;
  return s("g", {}, s("circle", { cx: 604, cy: 476, r: 20, fill: "#cfdcfd", stroke: "#ffffff", "stroke-width": 3 }),
    words(604, 477, "你", { "font-size": 16, "text-anchor": "middle", "dominant-baseline": "middle", fill: "#27325c", "font-weight": 700 }),
    hint(d.guest_line || "你在她屋里"));
}

function dark(d) {
  // her lamp is off while she sleeps at night: the room goes dim around her
  if (!(d.light === "night" && d.her.asleep && !d.her.out)) return null;
  return s("rect", { x: 268, y: 222, width: 532, height: 318, fill: "#141a40", opacity: .38, "pointer-events": "none" });
}

function shade(d) {
  // dusk and night outside; inside, the walls are lit by her lamp or dark when she sleeps (house())
  if (d.light === "day") return null;
  return s("rect", { x: 0, y: 0, width: 1000, height: 600, fill: "#141a40", opacity: d.light === "night" ? .3 : .1,
    "pointer-events": "none" });
}

function picture(d) {
  ID = `w${++drawn}-`;
  const svg = s("svg", { viewBox: "0 0 1000 600", role: "img", class: "cottage-picture",
    "aria-label": `她的小屋：${d.her.out ? AWAY_WORDS[d.her.out] : d.her.asleep ? "她在睡觉" : "她在" + d.her.doing}` });
  for (const part of [defs(d.light), sky(d), land(d), weather(d), shade(d), house(d), bed(d), heater(d), kitchen(d), sill(d), dark(d), him(d), her(d)])
    if (part) svg.append(part);
  return svg;
}

// --- the window, with words under it ---------------------------------------------------------

function caption(d, el) {
  const out = d.her.out ? AWAY_WORDS[d.her.out] : "";
  const now = out || (d.her.asleep ? "在睡觉" : d.her.doing === "闲着" ? "这会儿闲着" : `在${d.her.doing}`);
  const lines = Object.values(d.words).filter(Boolean);
  if (d.guest_line) lines.unshift(d.guest_line);
  return el("div", "window-words",
    el("div", "window-now round", `她${now}` + (d.her.until ? `，大概到 ${d.her.until}` : "")),
    d.mood ? el("div", "note", "心情：" + d.mood) : null,
    d.weather ? el("div", "note", "外面：" + d.weather) : null,
    el("ul", "plain", ...lines.map(x => el("li", "", x))),
    d.today.length ? el("div", "window-today",
      el("div", "note", "屋里今天的事"),
      el("ul", "timeline", ...d.today.map(e => el("li", "", el("span", "when", e.when), el("span", "what", e.text))))) : null,
    el("div", "note", "把鼠标停在屋里的东西上，能看到它现在怎么样。一分钟自己刷新一次。"));
}

window.drawCottage = function (d, el) {
  return el("div", "window-card card", el("div", "window-frame", picture(d)), caption(d, el));
};
