// Build <First-Last>-Cover-Letter.docx and .html from a plain-paragraph cover-letter.md.
// The base name is derived from the master resume's "# Name" line, e.g. "Alex Q. Doe" -> Alex-Q-Doe-Cover-Letter.
// Usage: node build-letter.js <cover-letter.md> <master-resume.md> <outDir> [file-stem]
// The header (name and contact line) comes from the master resume so it always matches.
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, AlignmentType } = require('docx');

const [, , src, master, outDir, stemArg] = process.argv;
const m = fs.readFileSync(master, 'utf8').replace(/^\uFEFF/, '').split('\n').map((l) => l.trim());
const name = m.find((l) => l.startsWith('# ')).slice(2);
const contact = m[3];
const paras = fs.readFileSync(src, 'utf8').replace(/^\uFEFF/, '').replace(/\r/g, '').split(/\n\s*\n/)
  .map((p) => p.replace(/\s*\n\s*/g, '\n').trim()).filter(Boolean);
const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

const FONT = 'Arial';
const run = (text, opts = {}) => new TextRun({ text, font: FONT, size: 21, ...opts });
// Lines inside one paragraph (e.g. "Sincerely,\nYour Name") become line breaks.
const lineRuns = (p) => p.split('\n').flatMap((t, i) => (i ? [run(t, { break: 1 })] : [run(t)]));

const kids = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 20 }, children: [run(name, { bold: true, size: 32 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [run(contact, { size: 18 })] }),
  new Paragraph({ spacing: { after: 240 }, children: [run(today)] }),
  ...paras.map((p) => new Paragraph({ spacing: { after: 200, line: 276 }, children: lineRuns(p) })),
];
const doc = new Document({
  creator: name, title: `${name} Cover Letter`,
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 },
    margin: { top: 1080, bottom: 1080, left: 1260, right: 1260 } } }, children: kids }],
});
const base = path.join(outDir, (stemArg || name.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'Your-Name') + '-Cover-Letter');
Packer.toBuffer(doc).then((buf) => fs.writeFileSync(`${base}.docx`, buf));

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const css = `@page{size:Letter;margin:0.75in 0.875in}
body{font-family:Arial,sans-serif;font-size:10.5pt;line-height:1.38;color:#111;margin:0}
h1{font-size:16pt;text-align:center;margin:0 0 1pt}.contact{text-align:center;font-size:9pt;margin:0 0 22pt}
p{margin:0 0 10pt}`;
fs.writeFileSync(`${base}.html`, `<!doctype html><html><head><meta charset="utf-8"><title>${esc(name)} Cover Letter</title><style>${css}</style></head><body>`
  + `<h1>${esc(name)}</h1><p class="contact">${esc(contact)}</p><p>${today}</p>`
  + paras.map((p) => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`).join('') + '</body></html>');
