// The scenarios of @blender-ui/react's and @blender-ui/svelte's tests, in Vue 3, and what Vue adds:
// v-model, v-for with keys, slots, provide/inject, scoped styles, lifecycle, plugins, TypeScript.
import test from 'node:test'
import assert from 'node:assert'
import { render, createApp, createRoot, h, ref, onMounted, onUnmounted, nextTick, withModifiers, withKeys, Teleport, signal, Button } from '../index.js'
import native from '@blender-ui/native'
import { compileVue } from '../compile.js'
import Counter from './fixtures/Counter.vue'
import Form from './fixtures/Form.vue'
import List from './fixtures/List.vue'
import Cards from './fixtures/Cards.vue'
import Show from './fixtures/Show.vue'
import Scoped from './fixtures/Scoped.vue'
import Plain from './fixtures/Plain.vue'
import Typed from './fixtures/Typed.vue'

const tick = (ms = 30) => new Promise((r) => setTimeout(r, ms))
const at = (s, x, y) => { const i = (y * s.width + x) * 4; return [...s.data.subarray(i, i + 3)] }
const finder = (window) => (id) => [...window._nodes.values()].find((n) => n.getAttribute?.('id') === id)
const elements = (el) => el.childNodes.filter((n) => n.nodeType === 1)
const open = (t, component, options = {}) => {
  const r = render(component, { headless: true, width: 240, height: 160, ...options })
  if (!options.app) t.after(() => r.app.quit()) // one App at a time: a test that opens more shares the first's
  r.window.body.style = 'margin: 0; background: #000'
  return r
}
/** One rendered frame: the native side hit-tests against the last layout. */
const settle = async (window) => { await tick(); await window.screenshot() }

test('Vue: render, state, events, styles, conditional children (headless)', async (t) => {
  const { window } = open(t, Counter)
  await settle(window)
  const find = finder(window)
  const box = find('box')
  assert.strictEqual(box.textContent.trim(), 'count 0')
  let shot = await window.screenshot()
  assert.deepStrictEqual(at(shot, 70, 20), [0, 0, 255])
  window.click(30, 20)
  await tick()
  assert.strictEqual(box.textContent.trim(), 'count 1', 'a ref changed the text')
  shot = await window.screenshot()
  assert.deepStrictEqual(at(shot, 70, 20), [0, 255, 0], 'the :style object updated')
  assert.ok(find('extra'), 'v-if mounted its element')
  const extra = find('extra')
  window.click(30, 20)
  await tick()
  assert.strictEqual(box.textContent.trim(), 'count 2')
  assert.strictEqual(find('extra'), extra, 'the element stayed (same node)')
})

test('Vue: Blender widgets are components', async (t) => {
  const { window } = open(t, Counter)
  await settle(window)
  const find = finder(window)
  const b = find('b')
  assert.ok(b, 'the Button rendered')
  assert.strictEqual(b.textContent, 'Add ten', 'its slot is the label')
  assert.strictEqual(b.getAttribute('bui-blender'), '', 'a Blender widget, not a browser button')
  b._dispatch({ kind: 'click' })
  await tick()
  assert.strictEqual(find('box').textContent.trim(), 'count 10', '@click reached the widget once (not twice)')
})

test('Vue: v-model on inputs, checkboxes, radios, selects and widgets', async (t) => {
  const { window } = open(t, Form)
  await settle(window)
  const find = finder(window)
  const out = () => find('out').textContent
  assert.strictEqual(out(), '|false|red|b|m|2:number||1:number||3:number', 'initial values')
  assert.strictEqual(find('rb').checked, true, 'the radio whose value matches is checked')
  assert.strictEqual(find('red').checked, true, 'a checkbox in the array is checked')
  assert.strictEqual(find('blue').checked, false)
  assert.strictEqual(find('size').value, 'm')
  assert.strictEqual(find('n').value, '2', 'a slider shows its number')

  find('name')._dispatch({ kind: 'input', value: 'Ada' })
  find('agree')._dispatch({ kind: 'change', checked: true })
  find('blue')._dispatch({ kind: 'change', checked: true })
  find('ra')._dispatch({ kind: 'change', checked: true })
  find('size')._dispatch({ kind: 'change', value: 's' })
  find('n')._dispatch({ kind: 'input', value: '7' })
  find('trimmed')._dispatch({ kind: 'input', value: '  hi  ' })
  find('count')._dispatch({ kind: 'input', value: '42' })
  find('ta')._dispatch({ kind: 'input', value: 'line one' })
  find('num')._dispatch({ kind: 'input', value: '12.5' })
  await tick()
  assert.strictEqual(out(), 'Ada|true|red+blue|a|s|7:number|hi|42:number|line one|12.5:number')
  assert.strictEqual(find('ta').value, 'line one', 'a textarea')
  assert.strictEqual(find('wagree').checked, true, 'two controls on one ref agree')
  assert.strictEqual(find('rb').checked, false, 'the other radio cleared')

  find('red')._dispatch({ kind: 'change', checked: false })
  find('agree')._dispatch({ kind: 'change', checked: false })
  await tick()
  assert.strictEqual(out(), 'Ada|false|blue|a|s|7:number|hi|42:number|line one|12.5:number', 'removed from the array; unchecked')
})

test('Vue: v-for with keys keeps and moves nodes; v-if / v-else-if / v-else; fragments', async (t) => {
  const { window, component } = open(t, List)
  await settle(window)
  const find = finder(window)
  const [l1, l2, l3] = [find('li1'), find('li2'), find('li3')]
  assert.deepStrictEqual(elements(find('list')).map((e) => e.textContent), ['one', 'two', 'three'])
  assert.ok(find('some') && !find('none') && !find('empty'))
  component.reverse()
  await tick()
  assert.deepStrictEqual(elements(find('list')).map((e) => e.textContent), ['three', 'two', 'one'])
  assert.deepStrictEqual([find('li1'), find('li2'), find('li3')], [l1, l2, l3], 'moved, not recreated')
  component.drop()
  await tick()
  assert.deepStrictEqual(elements(find('list')).map((e) => e.textContent), ['two', 'one'])
  assert.strictEqual(find('li3'), undefined, 'the removed item is gone natively too')
  component.empty = true
  await nextTick()
  await tick()
  assert.ok(!find('some'), 'v-else gave way to v-else-if')
})

test('Vue: slots, named slots, props with defaults, emits, provide / inject', async (t) => {
  const { window } = open(t, Cards)
  await settle(window)
  const find = finder(window)
  assert.strictEqual(find('card-a').querySelector?.('h3') ?? elements(find('card-a'))[0].textContent, 'a', 'the head slot falls back to the title')
  const b = find('card-b')
  assert.strictEqual(elements(b)[0].textContent, 'head b', 'a named slot')
  assert.strictEqual(elements(b)[1].textContent, 'second', 'the default slot')
  assert.ok(find('card-untitled'), 'a prop default')
  assert.match(b.getAttribute('class'), /\bcard\b.*\bdark\b/, 'inject got the provided value')
  find('card-b')._dispatch({ kind: 'click' })
  await tick()
  assert.strictEqual(find('picked').textContent, 'b', 'an emitted event reached the parent')
})

test('Vue: Teleport to an element', async (t) => {
  const dest = native.document.createElement('div')
  dest.setAttribute('id', 'dest')
  const Comp = {
    render: () => h('section', { id: 'src' }, [h(Teleport, { to: dest }, [h('i', { id: 'tele' }, 'moved')])]),
  }
  const { window } = open(t, Comp)
  window.body.appendChild(dest)
  await settle(window)
  const find = finder(window)
  assert.strictEqual(find('tele').parentNode, dest, 'the content is under the teleport target')
  assert.strictEqual(elements(find('src')).length, 0, 'and not where it was written')
})

test('Vue: v-show and :class', async (t) => {
  const { window } = open(t, Show)
  await settle(window)
  const find = finder(window)
  let shot = await window.screenshot()
  assert.deepStrictEqual(at(shot, 10, 10), [255, 0, 0], 'shown')
  assert.deepStrictEqual(at(shot, 10, 30), [0, 0, 255], 'the class object: cold')
  find('toggle')._dispatch({ kind: 'click' })
  await tick()
  assert.match(find('a').getAttribute('style'), /display:\s*none/, 'v-show wrote display: none through el.style')
  shot = await window.screenshot()
  assert.notDeepStrictEqual(at(shot, 10, 10), [255, 0, 0], 'hidden: not painted')
  assert.strictEqual(find('b').getAttribute('class'), 'hot', 'the class object changed')
  find('toggle')._dispatch({ kind: 'click' })
  await tick()
  assert.doesNotMatch(find('a').getAttribute('style'), /none/, 'shown again')
})

test('Vue: scoped styles apply to the component\'s own elements only', async (t) => {
  const outer = { render: () => h(Scoped, null, { default: () => h('div', { id: 'slotted', class: 'swatch', style: 'width: 40px; height: 20px' }) }) }
  const { window } = open(t, outer)
  await settle(window)
  const find = finder(window)
  assert.ok(find('mine').getAttributeNames().some((n) => n.startsWith('data-v-')), 'the scope attribute is set')
  const shot = await window.screenshot()
  assert.deepStrictEqual(at(shot, 10, 10), [255, 0, 255], 'the scoped rule paints the component\'s element')
  assert.deepStrictEqual(at(shot, 10, 30), [0, 0, 0], 'an element of the parent with the same class is outside the scope')
  const styles = window.body.childNodes.filter((n) => n.localName === 'style').map((n) => n.textContent)
  assert.strictEqual(styles.filter((css) => /\.swatch\[data-v-/.test(css)).length, 1, 'one <style> for the component, scoped')
})

test('Vue: a <script> component, a TypeScript <script setup>', async (t) => {
  const plain = open(t, Plain, { props: { label: 'hello' } })
  await settle(plain.window)
  const p = finder(plain.window)('plain')
  assert.strictEqual(p.textContent, 'hello 0', 'props and data in the options API')
  p._dispatch({ kind: 'click' })
  await tick()
  assert.strictEqual(p.textContent, 'hello 1', 'a method ran')

  const typed = open(t, Typed, { props: { start: 9 }, app: plain.app })
  await settle(typed.window)
  const el = finder(typed.window)('typed')
  assert.strictEqual(el.textContent, '9', 'types stripped, defineProps<Props>() runtime props')
  el._dispatch({ kind: 'click' })
  await tick()
  assert.strictEqual(el.textContent, '10')
})

test('Vue: events: once, stop, an array of handlers, a replaced handler, keys', async (t) => {
  const log = []
  const handlers = ref([() => log.push('a')])
  const Comp = {
    setup () {
      return () => h('div', { id: 'outer', onClick: () => log.push('outer') }, [
        h('div', { id: 'once', onClickOnce: () => log.push('once') }),
        h('div', { id: 'many', onClick: handlers.value }),
        h('div', { id: 'key', onKeydown: (e) => log.push(`key:${e.key}`) }),
      ])
    },
  }
  const { window } = open(t, Comp)
  await settle(window)
  const find = finder(window)
  find('once')._dispatch({ kind: 'click' })
  find('once')._dispatch({ kind: 'click' })
  assert.deepStrictEqual(log.splice(0), ['once', 'outer', 'outer'], 'once ran once; the click still bubbled both times')
  find('many')._dispatch({ kind: 'click' })
  assert.deepStrictEqual(log.splice(0), ['a', 'outer'], 'an array of handlers')
  handlers.value = [() => log.push('b'), () => log.push('c')]
  await nextTick()
  find('many')._dispatch({ kind: 'click' })
  assert.deepStrictEqual(log.splice(0), ['b', 'c', 'outer'], 'the handlers were replaced, not added')
  find('key')._dispatch({ kind: 'keydown', key: 'Enter' })
  assert.deepStrictEqual(log.splice(0), ['key:Enter'])
})

test('Vue: event modifiers (.stop, .self, .enter) as templates compile them', async (t) => {
  const log = []
  const Comp = {
    setup () {
      return () => h('div', { id: 'outer', onClick: () => log.push('outer') }, [
        h('div', { id: 'stop', onClick: withModifiers(() => log.push('stop'), ['stop']) }),
        h('div', { id: 'self', onClick: withModifiers(() => log.push('self'), ['self']) }, [h('i', { id: 'inner' })]),
        h('div', { id: 'enter', onKeydown: withKeys(() => log.push('enter'), ['enter']) }),
      ])
    },
  }
  const { window } = open(t, Comp)
  await settle(window)
  const find = finder(window)
  find('stop')._dispatch({ kind: 'click' })
  assert.deepStrictEqual(log.splice(0), ['stop'], '.stop kept the click from the parent')
  find('self')._dispatch({ kind: 'click' })
  assert.deepStrictEqual(log.splice(0), ['self', 'outer'])
  find('enter')._dispatch({ kind: 'keydown', key: 'a' })
  find('enter')._dispatch({ kind: 'keydown', key: 'Enter' })
  assert.deepStrictEqual(log.splice(0), ['enter'], '.enter ignored other keys')
})

test('Vue: createApp, plugins, render(app), createRoot; unmounting when the window closes', async (t) => {
  const events = []
  const Child = { setup () { onMounted(() => events.push('mounted')); onUnmounted(() => events.push('unmounted')); return () => h('div', { id: 'child' }, 'hi') } }
  const plugin = { install (app, options) { app.provide('who', options.who) } }
  const Root = { inject: ['who'], render () { return h('p', { id: 'who' }, [this.who, h(Child)]) } }
  const app = createApp(Root).use(plugin, { who: 'plugin' })
  const app_ = open(t, app)
  const { window, component } = app_
  await settle(window)
  const find = finder(window)
  assert.strictEqual(find('who').childNodes[0].textContent, 'plugin', 'a plugin provided a value')
  assert.deepStrictEqual(events, ['mounted'])
  assert.ok(component, 'render returns the root instance')
  window.close()
  await tick()
  assert.deepStrictEqual(events, ['mounted', 'unmounted'], 'closing the window unmounted the app')

  const second = open(t, { render: () => h('b', { id: 'one' }, 'one') }, { app: app_.app })
  const root = createRoot(second.window)
  root.render({ render: () => h('b', { id: 'two' }, 'two') })
  await tick()
  const find2 = finder(second.window)
  assert.ok(find2('two') && !find2('one'), 'a root replaces what it showed')
})

test('Vue: BUI signals bind attributes; the component does not re-render', async (t) => {
  const color = signal('#0000ff')
  let renders = 0
  const Comp = { render () { renders++; return h('div', { id: 'sig', style: 'width: 40px; height: 20px', class: color.value ? undefined : '' , 'data-c': color }) } }
  const { window } = open(t, Comp)
  await settle(window)
  const el = finder(window)('sig')
  assert.strictEqual(el.getAttribute('data-c'), '#0000ff')
  color.value = '#ff0000'
  await tick()
  assert.strictEqual(el.getAttribute('data-c'), '#ff0000', 'the signal updated the attribute')
  assert.strictEqual(renders, 1, 'without a render')
})

test('Vue: Button, and what compile.js does to a template', () => {
  assert.strictEqual(typeof Button, 'function')
  const code = (src) => compileVue(src, 'x.vue').code
  const model = code('<template><input v-model="x"><input type="checkbox" v-model="y"></template>')
  assert.doesNotMatch(model, /vModelText|vModelCheckbox/, 'v-model is the core transform: no DOM directives')
  assert.match(model, /modelValue/)
  const big = '<template><div>' + '<p>static text</p>'.repeat(40) + '</div></template>'
  assert.doesNotMatch(code(big), /createStaticVNode/, 'no static HTML strings: there is no HTML parser to insert them with')
  assert.throws(() => code('<template><div/></template><style lang="scss">a { b { c: d } }</style>'), /scss/)
  assert.match(code('<template><div/></template><style scoped>.a{color:red}</style>'), /addStyle[\s\S]*data-v-/)
})
