/* scale.js - pure ingredient-scaling helpers (no DOM, no dependencies).
 *
 * Rules (kept deliberately conservative; unparseable text is left untouched):
 *  - Only lines that START with a quantity are scaled; "Salt to taste" or
 *    "Juice of 1 lemon" are left alone.
 *  - The leading quantity is scaled, plus later "<number> <measuring unit>"
 *    pairs such as "(scant 3/4 cup)" or "plus 2 tablespoons".
 *  - A package-size descriptor directly after the leading quantity is NOT
 *    scaled: "2 (14 oz) cans" -> "4 (14 oz) cans", "2 x 400g tins" -> "4 x 400g tins".
 *  - Lines ending in ":" with no leading number are section headers.
 */
const UF_VALUES = {
  "½": 1 / 2, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 1 / 4, "¾": 3 / 4, "⅕": 0.2, "⅖": 0.4,
  "⅗": 0.6, "⅘": 0.8, "⅙": 1 / 6, "⅚": 5 / 6, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
};
const UF = Object.keys(UF_VALUES).join("");

// One number: mixed "1 1/2" / "1-1/2", fraction, decimal, "1½", "½", or integer.
const NUM = String.raw`(?:\d+[ \-]\d+\/\d+|\d+\/\d+|\d+\.\d+|\d+[${UF}]|[${UF}]|\d+)`;
const SEP = String.raw`(?:\s*[-–—]\s*|\s+to\s+)`;
const RANGE = `${NUM}(?:${SEP}${NUM})?`;
const UNIT = String.raw`(?:teaspoons?|tsps?|tablespoons?|tbsps?|tbs|cups?|ounces?|oz|pounds?|lbs?|grams?|g|kilograms?|kgs?|milliliters?|millilitres?|ml|liters?|litres?|l|quarts?|qts?|pints?|pts?|gallons?|gals?|sticks?)\.?(?![A-Za-z])`;
const NOT_PART_OF_WORD = String.raw`(?<![A-Za-z0-9./])`;

const SINGLE_RE = new RegExp(`^${NUM}$`);
const PAIR_RE = new RegExp(`^(${NUM})(${SEP})(${NUM})$`);
const LEAD_RE = new RegExp(`^(${RANGE})(?![%°º])`);
const SIZE_X_RE = new RegExp(`^\\s*[x×]\\s*${RANGE}\\s*${UNIT}`, "i");
const FIRST_RE = new RegExp(`${NOT_PART_OF_WORD}(${RANGE})`);

function parseNum(text) {
  const s = text.trim();
  let m;
  if ((m = /^(\d+)[ \-](\d+)\/(\d+)$/.exec(s))) return +m[3] ? { v: +m[1] + m[2] / m[3], style: "fraction" } : null;
  if ((m = /^(\d+)\/(\d+)$/.exec(s))) return +m[2] ? { v: m[1] / m[2], style: "fraction" } : null;
  if (/^\d+\.\d+$/.test(s)) return { v: parseFloat(s), style: "decimal" };
  if ((m = new RegExp(`^(\\d+)([${UF}])$`).exec(s))) return { v: +m[1] + UF_VALUES[m[2]], style: "fraction" };
  if (UF_VALUES[s] !== undefined) return { v: UF_VALUES[s], style: "fraction" };
  if (/^\d+$/.test(s)) return { v: parseInt(s, 10), style: "int" };
  return null;
}

const trimZeros = (s) => (s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s);

/** Format a scaled value the way a cook would write it ("1 1/2", "3/4", "33"). */
export function formatNumber(v, style = "int") {
  if (!Number.isFinite(v) || v < 0) return String(v);
  if (v >= 10) return style === "decimal" ? trimZeros(v.toFixed(1)) : String(Math.round(v));
  const near = Math.round(v);
  if (near > 0 && Math.abs(v - near) < 0.02) return String(near);
  if (style !== "decimal") {
    const whole = Math.floor(v);
    const frac = v - whole;
    let best = null;
    for (const d of [2, 3, 4, 8]) {
      for (let n = 1; n < d; n++) {
        const diff = Math.abs(frac - n / d);
        if (diff < 0.03 && (!best || diff < best.diff - 1e-9)) best = { n, d, diff };
      }
    }
    if (best) return (whole ? `${whole} ` : "") + `${best.n}/${best.d}`;
  }
  return trimZeros(v.toFixed(2));
}

export const formatFactor = (f) => `${formatNumber(f, "fraction")}×`;

function scaleRangeText(text, factor) {
  if (SINGLE_RE.test(text)) {
    const a = parseNum(text);
    return a ? formatNumber(a.v * factor, a.style) : text;
  }
  const m = PAIR_RE.exec(text);
  if (!m) return text;
  const a = parseNum(m[1]);
  const b = parseNum(m[3]);
  if (!a || !b) return text;
  return formatNumber(a.v * factor, a.style) + m[2] + formatNumber(b.v * factor, b.style);
}

export function isHeader(line) {
  const t = line.trim();
  return t.endsWith(":") && !new RegExp(`^[\\d${UF}]`).test(t);
}

function scaleRest(rest, factor) {
  let skipEnd = 0;
  let d = /^\s*\([^)]*\)/.exec(rest);
  if (d) skipEnd = d[0].length;
  else if ((d = SIZE_X_RE.exec(rest))) skipEnd = d[0].length;

  const re = new RegExp(`${NOT_PART_OF_WORD}(${RANGE})(\\s*)(${UNIT})`, "gi");
  let out = "";
  let last = 0;
  let m;
  while ((m = re.exec(rest))) {
    if (m.index < skipEnd) continue; // inside the protected package-size descriptor
    out += rest.slice(last, m.index) + scaleRangeText(m[1], factor) + m[2] + m[3];
    last = m.index + m[0].length;
  }
  return out + rest.slice(last);
}

/**
 * Scale one ingredient line.
 * Returns { kind: "header"|"item", segments: [{ text, lead }] } where the single
 * segment flagged `lead` is the leading quantity (rendered bold, like Paprika).
 */
export function scaleLine(line, factor = 1) {
  const s = line.trim();
  if (isHeader(s)) return { kind: "header", segments: [{ text: s.replace(/:$/, ""), lead: false }] };
  const m = LEAD_RE.exec(s);
  if (!m) return { kind: "item", segments: [{ text: s, lead: false }] };
  const same = factor === 1;
  const lead = same ? m[1] : scaleRangeText(m[1], factor);
  const rest = s.slice(m[0].length);
  return {
    kind: "item",
    segments: [{ text: lead, lead: true }, { text: same ? rest : scaleRest(rest, factor), lead: false }],
  };
}

/** Scale the first number in free text such as servings: "30 slices (2 loaves)". */
export function scaleFirstNumber(text, factor) {
  if (!text || factor === 1) return text;
  const m = FIRST_RE.exec(text);
  if (!m) return text;
  return text.slice(0, m.index) + scaleRangeText(m[1], factor) + text.slice(m.index + m[1].length);
}

/** Split directions into steps and sub-headings; strips existing "1." numbering. */
export function parseDirections(text) {
  const lines = String(text || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const numbered = lines.filter((l) => /^(step\s*)?\d+[.)]\s/i.test(l)).length > lines.length / 2;
  return lines.map((l) =>
    l.length <= 80 && l.endsWith(":")
      ? { kind: "header", text: l.slice(0, -1) }
      : { kind: "step", text: numbered ? l.replace(/^(step\s*)?\d+[.)]\s*/i, "") : l }
  );
}

export const splitLines = (text) => String(text || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
