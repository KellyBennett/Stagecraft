const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../stagecraft/web/index.html'), 'utf8');
const source = html.match(/<script id="session-gate">([\s\S]*?)<\/script>/)[1];
const createSessionGate = vm.runInNewContext(source + '\ncreateSessionGate');

test('loading and first save control when finishing becomes available', () => {
  const session = createSessionGate();
  assert.equal(session.begin('save'), false);
  assert.equal(session.begin('finish'), false);
  session.load(false);
  assert.equal(session.begin('finish'), false);
  assert.equal(session.begin('save'), true);
  session.complete('save', false);
  assert.equal(session.canSave, true);
  assert.equal(session.canFinish, false);
  assert.equal(session.begin('save'), true);
  session.complete('save', true);
  assert.equal(session.canFinish, true);
});

test('saving and finishing exclude each other and failures permit retry', () => {
  const session = createSessionGate();
  session.load(true);
  for (const action of ['save', 'finish']) {
    assert.equal(session.begin(action), true);
    assert.equal(session.canSave, false);
    assert.equal(session.canFinish, false);
    assert.equal(session.begin('save'), false);
    assert.equal(session.begin('finish'), false);
    session.complete(action, false);
    assert.equal(session.canSave, true);
    assert.equal(session.canFinish, true);
  }
});

test('successful finish permanently prevents further requests', () => {
  const session = createSessionGate();
  session.load(true);
  assert.equal(session.begin('finish'), true);
  session.complete('finish', true);
  session.complete('save', true);
  assert.equal(session.canSave, false);
  assert.equal(session.canFinish, false);
  assert.equal(session.begin('save'), false);
  assert.equal(session.begin('finish'), false);
});

test('all browser scripts have valid JavaScript syntax', () => {
  for (const match of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)) {
    new vm.Script(match[1]);
  }
});
