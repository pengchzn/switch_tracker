const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../script.js'), 'utf8');

function harness() {
    const elements = new Map();
    const element = () => ({
        children: [], textContent: '', style: {},
        set innerHTML(value) { this.html = value; this.children = []; },
        get innerHTML() { return this.html || ''; },
        appendChild(child) { this.children.push(child); },
    });
    const getElementById = id => {
        if (!elements.has(id)) elements.set(id, element());
        return elements.get(id);
    };
    const context = vm.createContext({
        console,
        document: { addEventListener() {}, getElementById, createElement: element },
        window: { location: { origin: 'http://localhost' } },
    });
    vm.runInContext(source, context);
    return { run: code => vm.runInContext(code, context), get: getElementById };
}

test('search can be cleared and recovered after no matches', () => {
    const h = harness();
    h.run(`updateGamesList([
        {titleName:'Zelda', originalName:'ゼルダ', totalPlayedMinutes:60},
        {titleName:'Mario', totalPlayedMinutes:30}
    ]); filterGames(' Zelda ');`);
    assert.equal(h.get('games-grid').children.length, 1);
    h.run(`filterGames('missing');`);
    assert.equal(h.get('games-grid').children.length, 0);
    h.run(`filterGames('ゼルダ');`);
    assert.equal(h.get('games-grid').children.length, 1);
    h.run(`filterGames('');`);
    assert.equal(h.get('games-grid').children.length, 2);
    assert.equal(h.run('gameData.length'), 2);
});

test('search, sort, and data refresh preserve view state', () => {
    const h = harness();
    h.run(`updateGamesList([
        {titleName:'Zelda B',totalPlayedMinutes:90},
        {titleName:'Zelda A',totalPlayedMinutes:30},
        {titleName:'Mario',totalPlayedMinutes:60}
    ]); sortGames('name'); filterGames('Zelda');`);
    assert.equal(h.get('games-grid').children.length, 2);
    assert.match(h.get('games-grid').children[0].innerHTML, /Zelda A/);
    h.run(`updateGamesList([...gameData,{titleName:'Zelda C',totalPlayedMinutes:120}]);`);
    assert.equal(h.get('games-grid').children.length, 3);
    assert.match(h.get('games-grid').children[0].innerHTML, /Zelda A/);
});
