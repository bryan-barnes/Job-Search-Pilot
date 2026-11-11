// Build <First-Last>-Resume.docx and .html from the master resume (resume/master.md).
// The base name is derived from the resume's "# Name" line, e.g. "Alex Q. Doe" -> Alex-Q-Doe-Resume.
// Usage: node build-resume.js <master-resume.md> <outDir> [file-stem]
// (tools/documents.py always passes the file stem, so Python and Node agree on file names.)
// Then print the HTML to PDF with headless Chrome (tools/documents.py does this).
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, BorderStyle, LevelFormat,
} = require('docx');

const [, , src, outDir, stemArg] = process.argv;
const raw = fs.readFileSync(src, 'utf8').replace(/^\uFEFF/, ''); // Notepad may add a BOM

const FONT = 'Arial';
const BODY = 19; // half-points (9.5pt)

const clean = (s) => s
  .replace(/\s*\[check[^\]]*\]/g, '')
  .replace(/((?:[A-Z][a-z]+ )?\d{4}) - (Present|(?:[A-Z][a-z]+ )?\d{4})/g, '$1 – $2');

// Split "**bold** rest" into [{text, bold}]
const segs = (s) => clean(s).split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((t) =>
  t.startsWith('**') ? { text: t.slice(2, -2), bold: true } : { text: t, bold: false });

const runs = (s, extra = {}) => segs(s).map((g) =>
  new TextRun({ text: g.text, bold: g.bold || extra.bold, font: FONT, size: extra.size || BODY }));

const html = (s) => segs(s).map((g) => {
  const t = g.text.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  return g.bold ? `<strong>${t}</strong>` : t;
}).join('');

const lines = raw.split('\n').map((l) => l.trimEnd());
const kids = [];
const h = [];

const name = lines.find((l) => l.startsWith('# ')).slice(2);
const headline = lines[2];
const contact = lines[3];

kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 20 },
  children: [new TextRun({ text: name, bold: true, font: FONT, size: 32 })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 20 },
  children: [new TextRun({ text: headline, font: FONT, size: 21 })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: contact, font: FONT, size: 18 })] }));
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
h.push(`<h1>${esc(name)}</h1><p class="headline">${esc(headline)}</p><p class="contact">${esc(contact)}</p>`);

for (let i = 4; i < lines.length; i++) {
  const l = lines[i];
  if (!l || l === '---' || l.startsWith('# ')) continue;
  if (l.startsWith('## ')) {
    const t = l.slice(3);
    kids.push(new Paragraph({
      spacing: { before: 140, after: 60 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '444444', space: 1 } },
      children: [new TextRun({ text: t, bold: true, font: FONT, size: 21 })],
    }));
    h.push(`<h2>${t}</h2>`);
  } else if (l.startsWith('### ')) {
    const t = l.slice(4);
    const next = lines[i + 1] && lines[i + 1].startsWith('**') ? lines[++i] : null;
    if (!next) { // e.g. "Earlier Experience"
      kids.push(new Paragraph({ spacing: { before: 100, after: 20 }, keepNext: true,
        children: [new TextRun({ text: t, bold: true, font: FONT, size: 20 })] }));
      h.push(`<h3>${t}</h3>`);
      continue;
    }
    kids.push(new Paragraph({ spacing: { before: 100, after: 0 }, keepNext: true,
      children: [new TextRun({ text: t, bold: true, font: FONT, size: 20 })] }));
    kids.push(new Paragraph({ spacing: { after: 30 }, keepNext: true, children: runs(next) }));
    h.push(`<h3>${t}</h3><p class="org">${html(next)}</p>`);
  } else if (l.startsWith('- ')) {
    kids.push(new Paragraph({ numbering: { reference: 'bullets', level: 0 },
      spacing: { after: 20 }, children: runs(l.slice(2)) }));
    // group consecutive bullets into one <ul>
    if (h.length && h[h.length - 1].endsWith('</ul>')) {
      h[h.length - 1] = h[h.length - 1].slice(0, -5) + `<li>${html(l.slice(2))}</li></ul>`;
    } else h.push(`<ul><li>${html(l.slice(2))}</li></ul>`);
  } else {
    kids.push(new Paragraph({ spacing: { after: 30 }, children: runs(l) }));
    h.push(`<p>${html(l)}</p>`);
  }
}

const doc = new Document({
  creator: name,
  title: `${name} Resume`,
  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET,
    text: '•', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 270, hanging: 200 } } } }] }] },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 },
    margin: { top: 605, bottom: 605, left: 792, right: 792 } } }, children: kids }],
});

const base = path.join(outDir, (stemArg || name.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'Your-Name') + '-Resume');
Packer.toBuffer(doc).then((buf) => fs.writeFileSync(`${base}.docx`, buf));

const css = `@page{size:Letter;margin:0.42in 0.55in}
body{font-family:Arial,sans-serif;font-size:9.5pt;line-height:1.18;color:#111;margin:0}
h1{font-size:16pt;text-align:center;margin:0 0 1pt}
.headline{text-align:center;font-size:10.5pt;margin:0 0 1pt}
.contact{text-align:center;font-size:9pt;margin:0 0 3pt}
h2{font-size:10.5pt;border-bottom:0.75pt solid #444;margin:7pt 0 3pt;padding-bottom:1pt}
h3{font-size:10pt;margin:5pt 0 0}
p{margin:0 0 1.5pt}.org{margin-bottom:1.5pt}
ul{margin:0 0 1pt;padding-left:13.5pt}li{margin:0 0 1pt}`;
fs.writeFileSync(`${base}.html`, `<!doctype html><html><head><meta charset="utf-8"><title>${esc(name)} Resume</title><style>${css}</style></head><body>${h.join('\n')}</body></html>`);
