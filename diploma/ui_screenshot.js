// ui_screenshot.js — Take screenshots of Adam Chip operator UI pages
const puppeteer = require(
  "C:/Users/XVII/AppData/Roaming/npm/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer-core"
);
const path = require("path");
const fs   = require("fs");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT    = path.join(__dirname, "assets", "ui");

const PAGES = [
  { url: "http://192.168.0.130:8080/ui/",                    file: "ui_main.png"      },
  { url: "http://192.168.0.130:8080/ui/templates/agent.html",file: "ui_agent.png"     },
  { url: "http://192.168.0.130:8080/ui/templates/dash.html", file: "ui_dash.png"      },
  { url: "http://192.168.0.130:8080/ui/templates/debug.html",file: "ui_debug.png"     },
  { url: "http://192.168.0.130:8083/",                       file: "ui_logviewer.png" },
];

const WIDTH  = 1600;
const HEIGHT = 900;

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--no-proxy-server"],
    defaultViewport: { width: WIDTH, height: HEIGHT },
  });

  for (const { url, file } of PAGES) {
    const out = path.join(OUT, file);
    process.stdout.write(`  ${url} -> ${file} ... `);
    try {
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: "networkidle2", timeout: 15000 });
      // Small pause so any dynamic content settles
      await new Promise(r => setTimeout(r, 1000));
      await page.screenshot({ path: out, fullPage: true });
      await page.close();
      console.log("ok");
    } catch (e) {
      console.log(`FAIL: ${e.message}`);
    }
  }

  await browser.close();
  console.log("Done.");
})();
