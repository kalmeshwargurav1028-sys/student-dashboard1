const fs = require('fs');
const html = fs.readFileSync('templates/base.html', 'utf8');
const scriptRegex = /<script.*?>([\s\S]*?)<\/script>/gi;
let match;
while ((match = scriptRegex.exec(html)) !== null) {
  try {
    new Function(match[1]);
  } catch (e) {
    console.error("Syntax Error found in base.html!");
    console.error(e);
  }
}
