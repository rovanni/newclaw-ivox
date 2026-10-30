// Inventário de licenças do que entra no build da janela (dependências de produção, transitivas incluídas).
// Uso (na pasta janela/): node ferramentas/licencas.mjs > ../docs/terceiros/janela.md
// Lê o package-lock.json e o package.json instalado de cada pacote; nada é inferido do nome.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const trava = JSON.parse(readFileSync('package-lock.json', 'utf8'));
const linhas = [];
for (const [caminho, info] of Object.entries(trava.packages)) {
  if (!caminho || info.dev) continue; // a raiz e as ferramentas de desenvolvimento não vão para o build
  const nome = caminho.replace(/^.*node_modules\//, '');
  const pj = join(caminho, 'package.json');
  let licenca = info.license;
  if (!licenca && existsSync(pj)) licenca = JSON.parse(readFileSync(pj, 'utf8')).license;
  linhas.push({ nome, versao: info.version, licenca: licenca || 'NÃO DECLARADA' });
}
linhas.sort((a, b) => a.nome.localeCompare(b.nome));
const contagem = {};
for (const l of linhas) contagem[l.licenca] = (contagem[l.licenca] || 0) + 1;

console.log('# Terceiros na janela de voz (build de `janela/`)\n');
console.log('Gerado por `janela/ferramentas/licencas.mjs` a partir do `package-lock.json`. Só dependências de produção (o que');
console.log('entra no build servido pelo harness); as de desenvolvimento (Vite, TypeScript, Vitest) não são distribuídas.\n');
console.log('| Licença | Pacotes |\n|---|---|');
for (const [l, n] of Object.entries(contagem).sort()) console.log(`| ${l} | ${n} |`);
console.log('\n| Pacote | Versão | Licença |\n|---|---|---|');
for (const l of linhas) console.log(`| ${l.nome} | ${l.versao} | ${l.licenca} |`);
