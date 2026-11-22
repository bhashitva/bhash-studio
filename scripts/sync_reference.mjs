// SPDX-License-Identifier: Apache-2.0
// node scripts/sync_reference.mjs <Bhash source checkout> <exact revision>
import fs from 'node:fs';
import path from 'node:path';
const [root, revision] = process.argv.slice(2);
if (!root || !/^[0-9a-f]{40}$/.test(revision || '')) throw Error('Supply a checkout and revision');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const identifierKey = value => value.normalize('NFC');
const identifierWord = /[\p{L}\p{M}\p{N}_\u200c\u200d]/u;
function moduleBody(name) {
  return read(name).replace(/^import .*;\r?\n/gm, '').replace(/^export \{[^}]*\};\r?\n/gm, '')
    .replace(/\bexport (?=(const|function)\b)/g, '');
}
const picker = new Function('identifierKey', 'identifierWord', moduleBody('playground/src/keyword-picker.mjs')
  + '\nreturn {keywordEntries,filterKeywords,keywordGroups};')(identifierKey, identifierWord);
const snippets = JSON.parse(read('editors/vscode/snippets/bhash.json'));
const language = new Function('snippets', 'keywordEntries', 'filterKeywords', 'keywordGroups',
  moduleBody('editors/jupyter/frontend/src/language-model.mjs') + '\nreturn {languageEntries};')
  (snippets, picker.keywordEntries, picker.filterKeywords, picker.keywordGroups);
const model = new Function('identifierKey', moduleBody('playground/src/library-model.mjs')
  + '\nreturn {libraryIndex,librarySnippet,signature};')(identifierKey);
const grammar = read('src/main/antlr4/Bhash.g4');
const words = [...grammar.matchAll(/^([A-Z_]+)\s*:\s*'([^']+)'\s*;/gm)]
  .filter(match => /\p{L}/u.test(match[2]) || match[1] === 'WILDCARD')
  .map(match => ({token:match[1], value:JSON.parse('"'+match[2]+'"')}));
words.push({token:'UNION_CONTEXTUAL', value:'विकल्पसमूह'}, {token:'MATCH_CONTEXTUAL', value:'मिलान'});
if (words.length !== 57) throw Error('Review changed grammar keyword inventory: '+words.length);
const data = JSON.parse(read('playground/public/library.json'));
const library = model.libraryIndex(data).entries.filter(({type,member}) => !type.internal && !member?.internal)
  .map(({type,member,label,search}) => ({label:label+(member?' · '+model.signature(type, member):''), search,
    group:type.group, kind:member?'members':'types', template:model.librarySnippet(type,member),
    detail:[model.signature(type,member),member?.english||type.english,member?.description||type.description,
      type.notes, 'ब्राउज़र लक्ष्य · '+type.browser, ...(type.examples||[])].filter(Boolean).join('\n\n'),
    example:type.examples?.[0]||'', path:type.reference||type.guide||''}));
const entries = language.languageEntries(words).map(entry => ({...entry,
  label:entry.value+' · '+entry.english, search:Object.values(entry).filter(v=>typeof v==='string').join(' '),
  detail:[entry.value,entry.english,entry.description,entry.template].join('\n\n'),
  path:'tutorial/jupyter-library-lookup/README.md'}));
fs.writeFileSync('bhash_studio/lookup_catalog.json', JSON.stringify({revision, compiler:'0.28.0', library, language:entries}, null, 2)+'\n');
const notes = {revision,types:{},methods:{},notes:{}};
for (const type of data.types) {
  notes.types[type.name] = type.description;
  notes.notes[type.name] = type.notes||type.description;
  for (const member of type.members) notes.methods[type.name+'.'+member.name] = member.description;
}
fs.writeFileSync('bhash_studio/stdlib_reference.json', JSON.stringify(notes, null, 2)+'\n');
console.log(`${data.types.length} types, ${library.length} reference entries, ${words.length} keywords, ${entries.length-words.length} constructs`);
