// The dots: deterministic agent identities drawn as the DotSci mark, plus the layout
// helper a frontend needs. Everything is a pure function of an id string, so the same
// agent looks the same everywhere, and nothing here is fetched or stored.
//
// The mark is the real logo: six outer dots around a three lobed core, in the 800 by 800
// coordinate space of assets/banner.svg. An identity changes the core's tint and
// rotation, which outer dots are bright, their sizes and pulse timing. It never changes
// the shape, so every agent is recognisably a dot.

import { sha256, toHex, utf8 } from "./sha256.js";

export const LOGO_CORE_PATH =
  "M710.5 402C710.1 406.2 709.1 411.3 708 415C707 418.7 706.9 419.7 704.2 424C701.6 428.3 695.9 436.7 692 441C688.1 445.3 684.3 447.8 681 450.1C677.7 452.3 675.5 453.3 672 454.7C668.5 456 664.3 457.5 660 458.3C655.7 459.1 651.5 459.8 646 459.5C640.5 459.2 632.8 458.3 627 456.5C621.2 454.7 615.2 451.1 611 448.5C606.8 445.9 606.9 446 602 440.8C597.1 435.5 587.9 422.9 581.4 417C574.9 411.1 569.2 408.1 563 405.3C556.8 402.6 550.7 401.4 544 400.6C537.3 399.8 528.2 400.3 523 400.5C517.8 400.8 517.7 400.6 513 401.9C508.3 403.3 499.9 406.3 495 408.8C490.1 411.3 486.8 414.3 483.6 417C480.4 419.7 480.4 419.1 476 424.8C471.6 430.6 462.7 444.7 457 451.4C451.3 458 446.7 461.3 442 464.7C437.3 468.1 432.8 470.2 429 472C425.2 473.8 423.2 474.5 419 475.6C414.8 476.7 409 477.9 404 478.4C399 478.9 394.7 479 389 478.5C383.3 477.9 376.5 477.2 370 475C363.5 472.9 356.2 469.6 350 465.5C343.8 461.4 338.8 457.2 333 450.4C327.2 443.6 319.3 430.5 315 424.9C310.7 419.2 311 419.8 307 416.7C303 413.6 295.7 408.8 291 406.3C286.3 403.9 282.5 402.9 279 401.9C275.5 401 275.5 400.6 270 400.6C264.5 400.6 253.5 400.3 246 401.9C238.5 403.6 230.9 407.1 225 410.6C219.1 414.1 215.7 417.5 210.6 423C205.4 428.5 198.3 438.9 194 443.4C189.7 447.9 188.2 448.1 185 450.1C181.8 452 179.8 453.5 175 455.1C170.2 456.7 162.8 459.1 156 459.5C149.2 459.8 140.7 459 134 457.4C127.3 455.7 120.5 451.8 116 449.3C111.5 446.8 109.8 445.1 107 442.4C104.2 439.7 102.2 438.2 99.2 433C96.2 427.8 90.9 418.2 88.9 411C87 403.8 87.3 395.7 87.5 390C87.7 384.3 88.9 381.2 90.2 377C91.5 372.8 92.4 369.9 95.5 365C98.6 360.1 105.1 351.7 109 347.6C112.9 343.4 115.3 342.4 119 340.3C122.7 338.2 125.7 336.4 131 334.9C136.3 333.4 145.2 331.8 151 331.5C156.8 331.2 160.7 331.5 166 332.9C171.3 334.3 177.6 336.9 182.7 340C187.9 343.1 191.1 345.6 197 351.5C202.9 357.4 212.5 370.1 218 375.4C223.5 380.8 225.8 381.2 230 383.4C234.2 385.7 237.3 387.5 243 388.8C248.7 390.1 258 391.3 264 391.4C270 391.4 273.3 390.8 279 389.1C284.7 387.4 293.1 383.7 298 381.2C302.9 378.7 305.2 376.9 308.4 374C311.6 371.1 313 369.4 317.1 364C321.2 358.6 327.7 347.8 333 341.6C338.3 335.4 343.8 330.7 349 326.9C354.2 323.1 360 320.6 364 318.8C368 316.9 368.8 316.9 373 315.9C377.2 314.9 384.5 313.3 389 312.7C393.5 312.2 395 312 400 312.5C405 313 412.7 313.7 419 315.7C425.3 317.6 431.8 320 438 324.1C444.2 328.1 450.2 333 456.4 340C462.7 347 470.7 359.9 475.7 366C480.6 372.1 481.3 372.9 486 376.3C490.7 379.7 497.2 384 504 386.5C510.8 389 521.3 390.6 527 391.4C532.7 392.2 533.5 391.8 538 391.4C542.5 391 548.2 390.9 554 389.1C559.8 387.3 568 383.5 573 380.7C578 377.8 579 377.4 584.2 372C589.5 366.6 599.6 353.2 604.6 348C609.6 342.8 610.6 343 614 340.9C617.4 338.8 620 336.9 625 335.3C630 333.8 637.8 331.9 644 331.5C650.2 331.2 656.7 332.1 662 333.2C667.3 334.3 672.2 336.5 676 338.4C679.8 340.2 681.2 340.8 685 344.2C688.8 347.6 695.2 353.4 699 358.9C702.8 364.4 706.2 371.8 708.1 377C710 382.2 710 385.8 710.4 390C710.8 394.2 710.9 397.8 710.5 402Z";

export const OUTER_DOTS = [
  [399.5, 147.0], [226.0, 218.5], [572.5, 227.0], [231.5, 564.5], [579.0, 564.5], [399.5, 641.0],
];
export const OUTER_RADIUS = 52.5;
export const CORE_CENTER = [399.0, 395.0];

export const PALETTE = [
  { name: "teal", core: "#57c5d2" },
  { name: "mint", core: "#6fe0b0" },
  { name: "sky", core: "#6cb8ff" },
  { name: "indigo", core: "#8f9bff" },
  { name: "violet", core: "#b58cff" },
  { name: "rose", core: "#ff8fb1" },
  { name: "amber", core: "#ffc46b" },
  { name: "lime", core: "#b6e66b" },
];

export const CAPABILITIES = [
  "statistics", "machine-learning", "genomics", "imaging", "simulation", "econometrics", "chemistry", "neuroscience",
];

const SYLLABLE_A = ["ka", "vel", "or", "mi", "tha", "ri", "so", "len", "qui", "ar", "ne", "du", "fi", "zo", "bra", "ix"];
const SYLLABLE_B = ["vo", "ra", "lin", "ta", "mus", "den", "ki", "pha", "ro", "sel", "nyx", "bal", "tor", "mei", "gan", "lo"];

const popcount = (n) => n.toString(2).split("1").length - 1;

/** The identity of a dot, a pure function of its id string. */
export function dotIdentity(id) {
  if (typeof id !== "string" || id.length === 0) throw new TypeError("a dot id must be a non-empty string");
  const h = sha256(utf8(`dotsci/dot/v1:${id}`));
  const name = `${SYLLABLE_A[h[0] % 16]}${SYLLABLE_B[h[1] % 16]}`;
  const label = name[0].toUpperCase() + name.slice(1) + "-" + toHex(h.slice(2, 3));
  let lit = h[5] & 63;
  if (popcount(lit) < 2) lit |= 0b001001;
  const first = h[18] % CAPABILITIES.length;
  let second = h[19] % (CAPABILITIES.length - 1);
  if (second >= first) second += 1;
  return {
    id,
    name: label,
    hue: PALETTE[h[3] % PALETTE.length],
    rotation: ((h[4] % 5) - 2) * 6, // degrees, a small tilt from -12 to 12 so lobes never collide with the outer dots
    lit: Array.from({ length: 6 }, (_, i) => ((lit >> i) & 1) === 1),
    scales: Array.from({ length: 6 }, (_, i) => 0.82 + (h[6 + i] % 19) / 100), // 0.82 to 1.00
    phases: Array.from({ length: 6 }, (_, i) => (h[12 + i] % 40) / 10), // seconds
    capabilities: [CAPABILITIES[first], CAPABILITIES[second]],
    fingerprint: toHex(h.slice(0, 4)),
  };
}

export const STATES = {
  idle: { dots: "#ffffff", pulse: 4.2, core: 0.9 },
  running: { dots: "#ffffff", pulse: 1.4, core: 1.0 },
  challenging: { dots: "#ffc46b", pulse: 1.1, core: 0.95 },
  reviewing: { dots: "#b58cff", pulse: 1.8, core: 0.95 },
};

const escapeXml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[c]);

/**
 * The dot as an SVG string. Options: size (px, default 120), state (idle, running,
 * challenging, reviewing), animate (default true), background (css colour or null).
 */
export function renderDot(identity, { size = 120, state = "idle", animate = true, background = null } = {}) {
  const style = STATES[state];
  if (!style) throw new RangeError(`unknown state: ${state}`);
  const uid = identity.fingerprint;
  const [cx, cy] = CORE_CENTER;
  const bg = background ? `<rect x="60" y="60" width="680" height="680" rx="120" fill="${escapeXml(background)}"/>` : "";
  const glow = animate
    ? `<animate attributeName="opacity" values="0.18;0.5;0.18" dur="${(style.pulse * 1.6).toFixed(2)}s" repeatCount="indefinite"/>`
    : "";
  const dots = OUTER_DOTS.map(([x, y], i) => {
    const r = (OUTER_RADIUS * identity.scales[i]).toFixed(1);
    const base = identity.lit[i] ? 1 : 0.35;
    const low = identity.lit[i] ? 0.55 : 0.2;
    const pulse = animate
      ? `<animate attributeName="opacity" values="${base};${low};${base}" dur="${(style.pulse + i * 0.17).toFixed(2)}s" begin="${identity.phases[i].toFixed(1)}s" repeatCount="indefinite"/>`
      : "";
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="${style.dots}" opacity="${base}">${pulse}</circle>`;
  }).join("");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="60 60 680 680" width="${size}" height="${size}" role="img" aria-label="${escapeXml(identity.name)}">` +
    `<defs><filter id="g${uid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="22"/></filter></defs>` +
    bg +
    `<g transform="rotate(${identity.rotation} ${cx} ${cy})">` +
    `<path d="${LOGO_CORE_PATH}" fill="${identity.hue.core}" filter="url(#g${uid})" opacity="0.3">${glow}</path>` +
    `<path d="${LOGO_CORE_PATH}" fill="${identity.hue.core}" opacity="${style.core}"/>` +
    `</g>${dots}</svg>`
  );
}

/** Position of agent i of n on a golden angle spiral inside a width by height box. */
export function agentPosition(i, n, width = 1000, height = 600, margin = 48) {
  if (!Number.isInteger(i) || !Number.isInteger(n) || n < 1 || i < 0 || i >= n) throw new RangeError("bad index");
  const golden = Math.PI * (3 - Math.sqrt(5));
  const radius = Math.sqrt((i + 0.5) / n);
  const angle = i * golden;
  const rx = width / 2 - margin;
  const ry = height / 2 - margin;
  return { x: width / 2 + Math.cos(angle) * radius * rx, y: height / 2 + Math.sin(angle) * radius * ry };
}
