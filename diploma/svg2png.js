// svg2png.js -- Convert SVGs in assets/diagrams/ to PNG via Puppeteer
// Inline SVG into HTML to avoid file:// security restrictions.

const puppeteer = require(
  "C:/Users/XVII/AppData/Roaming/npm/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer-core"
);
const fs   = require("fs");
const path = require("path");

const CHROME      = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const DIAGRAMS    = path.join(__dirname, "assets", "diagrams");
const SCALE       = 2; // 2x for crisp rendering in Word (300 dpi equivalent)

function getDimensions(svgContent) {
  const vb = svgContent.match(/viewBox="([^"]+)"/);
  if (vb) {
    const p = vb[1].trim().split(/[\s,]+/);
    return { w: Math.ceil(parseFloat(p[2])), h: Math.ceil(parseFloat(p[3])) };
  }
  const w = svgContent.match(/width="([\d.]+)"/);
  const h = svgContent.match(/height="([\d.]+)"/);
  return {
    w: w ? Math.ceil(parseFloat(w[1])) : 800,
    h: h ? Math.ceil(parseFloat(h[1])) : 400,
  };
}

async function svgToPng(svgPath, pngPath) {
  const raw = fs.readFileSync(svgPath, "utf8");
  const { w, h } = getDimensions(raw);

  // Force white background on the SVG element itself
  const svgInlined = raw.replace(
    /background-color:\s*transparent/g,
    "background-color: white"
  );

  const html = `<!DOCTYPE html><html><head><style>
    * { margin: 0; padding: 0; }
    html, body { width: ${w}px; height: ${h}px; background: white; overflow: hidden; }
    svg { display: block; }
  </style></head><body>${svgInlined}</body></html>`;

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: w * SCALE, height: h * SCALE, deviceScaleFactor: SCALE });
  await page.setContent(html, { waitUntil: "networkidle0" });

  // Screenshot the SVG element directly (more accurate than full-page clip)
  const el = await page.$("svg");
  if (!el) throw new Error("SVG element not found in rendered page");

  await el.screenshot({ path: pngPath, omitBackground: false });
  await browser.close();
}

async function main() {
  const svgs = fs.readdirSync(DIAGRAMS).filter((f) => f.endsWith(".svg"));
  if (!svgs.length) { console.log("No SVGs found in", DIAGRAMS); return; }

  for (const f of svgs) {
    const src = path.join(DIAGRAMS, f);
    const dst = path.join(DIAGRAMS, f.replace(".svg", ".png"));
    process.stdout.write(`  ${f} -> ${path.basename(dst)} ... `);
    try {
      await svgToPng(src, dst);
      console.log("ok");
    } catch (e) {
      console.log("FAILED:", e.message);
    }
  }
  console.log("Done.");
}

main().catch((e) => { console.error(e); process.exit(1); });
