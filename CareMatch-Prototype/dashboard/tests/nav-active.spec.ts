import { test, expect } from '@playwright/test';

// WCAG relative luminance (standard formula, WCAG 2.x) from a CSS color.
// Accepts rgb(r, g, b), #hex, and oklch(L C H) — the last is what this
// app's design tokens actually resolve to (see styles.css :root).
function parseChannel(s: string): number {
  // rgb()
  const rgb = s.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
  if (rgb) {
    return [rgb[1], rgb[2], rgb[3]].map((v) => Number(v) / 255);
  }
  // #hex
  const hex = s.trim().match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }
  // oklch(L C H)
  const oklch = s.match(/oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/i);
  if (oklch) {
    const L = Number(oklch[1]);
    const C = Number(oklch[2]);
    const H = (Number(oklch[3]) * Math.PI) / 180;
    const a = C * Math.cos(H);
    const b = C * Math.sin(H);
    // OKLab -> linear sRGB
    const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
    const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
    const s_ = L - 0.0894841775 * a - 1.291485548 * b;
    const l = l_ ** 3;
    const m = m_ ** 3;
    const s = s_ ** 3;
    const r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
    const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
    const bl = -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s;
    // Gamma-encode back to sRGB so parseChannel() always returns
    // gamma-encoded sRGB (same convention as the rgb()/hex branches) and
    // relativeLuminance() applies the WCAG linearization exactly once.
    const enc = (c: number) =>
      c > 0.0031308 ? 1.055 * Math.pow(c, 1 / 2.4) - 0.055 : 12.92 * c;
    return [enc(r), enc(g), enc(bl)];
  }
  throw new Error(`Unhandled color format: ${s}`);
}

function relativeLuminance(color: string): number {
  const [r, g, b] = parseChannel(color);
  const lin = (c: number) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrastRatio(c1: string, c2: string): number {
  const l1 = relativeLuminance(c1);
  const l2 = relativeLuminance(c2);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

const pages = [
  { path: '/', activeLabel: 'New Assessment' },
  { path: '/review', activeLabel: 'Assessment Review' },
  { path: '/trials', activeLabel: 'Trials' },
];

for (const page of pages) {
  test(`active nav tab is "${page.activeLabel}" on ${page.path}`, async ({ page: p }) => {
    await p.goto(`http://localhost:8080${page.path}`);
    await p.waitForLoadState('networkidle');

    // Exactly ONE <nav> element renders on the page (the new Nav()
    // component; the old inline nav loop is gone).
    const allNavs = p.locator('nav');
    expect(await allNavs.count()).toBe(1);
    const nav = p.locator('nav[aria-label="Main navigation"]');
    await expect(nav).toBeVisible();

    // Exactly one nav link carries the active background class, and it is
    // the correct link for this page.
    const activeLinks = nav.locator('a.bg-white');
    expect(await activeLinks.count()).toBe(1);
    const activeText = (await activeLinks.first().textContent())?.trim();
    expect(activeText).toBe(page.activeLabel);

    // Extract the ACTUAL resolved colors from the live DOM and prove the
    // contrast mathematically (WCAG relative luminance), not visually.
    const headerBg = await p
      .locator('header')
      .first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    const activeBg = await activeLinks
      .first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    const activeColor = await activeLinks
      .first()
      .evaluate((el) => getComputedStyle(el).color);

    // Active tab: its text (dark structure color) sits on its white pill
    // background. This is the pair that was broken before the fix.
    const activeTabRatio = contrastRatio(activeColor, activeBg);
    // The white pill against the dark header it sits on.
    const pillOnHeaderRatio = contrastRatio(activeBg, headerBg);

    console.log(
      `[${page.path}] nav count=${await allNavs.count()} headerBg=${headerBg} ` +
        `activeLinks=${await activeLinks.count()} activeLabel="${activeText}" ` +
        `activeBg=${activeBg} activeColor=${activeColor} ` +
        `activeTabRatio=${activeTabRatio.toFixed(2)} pillOnHeaderRatio=${pillOnHeaderRatio.toFixed(2)}`,
    );

    // WCAG AA large-text threshold is 3:1; AA normal text is 4.5:1. The
    // active tab text is small (text-sm) so 4.5:1 is the bar. Both pairs
    // must clear it.
    expect(activeTabRatio).toBeGreaterThan(4.5);
    expect(pillOnHeaderRatio).toBeGreaterThan(4.5);
  });
}
