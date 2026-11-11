// Single-file components (`.vue`) for BUI: compiled with Vue's own compiler (`vue/compiler-sfc`),
// one place for the Node.js hooks (register.js) and the Bun plugin (plugin.js).
//
// What differs from a web build: the template compiler is Vue's DOM one with two changes. `v-model`
// is compiled with the core transform (props `modelValue` / `onUpdate:modelValue`, which model.js
// handles) because the DOM's `vModelText` and friends need a browser, and static hoisting into
// HTML strings (`createStaticVNode`) is off because there is no HTML parser to insert it with.
// `<style>` blocks are compiled by Vue (scoped ones get `[data-v-xxxx]` selectors) and handed to
// `addStyle`, which adds them to each window once.
//
// SPDX-License-Identifier: GPL-2.0-or-later
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const HERE = path.dirname(fileURLToPath(import.meta.url))

/** Single-file components. */
export const VUE_FILE = /\.vue$/
/** This package, as compiled components import it: always this copy (one registry of styles),
 *  installed next to them or not. */
export const SELF = /^@blender-ui\/vue$/
export const selfFile = () => path.join(HERE, 'index.js')

let sfc = null // vue/compiler-sfc, loaded on the first component (it is most of Vue's size)
let compiler = null

function load () {
  if (sfc !== null) return
  sfc = require('vue/compiler-sfc')
  const dom = createRequire(require.resolve('vue/package.json'))('@vue/compiler-dom')
  compiler = {
    ...dom,
    compile: (source, options) => dom.compile(source, {
      ...options,
      hoistStatic: false,
      directiveTransforms: { ...options.directiveTransforms, model: dom.transformModel },
    }),
  }
}

/** A 32-bit hash of `s` (FNV-1a) as 8 hex digits: the scope id of a component, from its path. */
function hash (s) {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 0x01000193)
  return (h >>> 0).toString(16).padStart(8, '0')
}

/**
 * The JavaScript of a `.vue` file. `lang="ts"` scripts come back as TypeScript when `keepTypes`
 * (Bun transpiles it), else with the types stripped (Node.js, `module.stripTypeScriptTypes`).
 * @returns {{ code: string, typescript: boolean }}
 */
export function compileVue (source, filename, { keepTypes = false } = {}) {
  load()
  const { descriptor, errors } = sfc.parse(source, { filename })
  if (errors.length > 0) throw errors[0]
  const id = hash(filename)
  const scopeId = `data-v-${id}`
  const scoped = descriptor.styles.some((s) => s.scoped)
  const typescript = [descriptor.script, descriptor.scriptSetup].some((s) => s?.lang === 'ts' || s?.lang === 'tsx')
  const templateOptions = { compiler, scoped, id, compilerOptions: { scopeId: scoped ? scopeId : undefined } }

  const out = []
  if (descriptor.script || descriptor.scriptSetup) {
    const script = sfc.compileScript(descriptor, {
      id, inlineTemplate: descriptor.scriptSetup != null, templateOptions,
    })
    out.push(sfc.rewriteDefault(script.content, '_sfc_main', typescript ? ['typescript'] : undefined))
  } else {
    out.push('const _sfc_main = {}')
  }
  if (descriptor.template && !descriptor.scriptSetup) {
    const t = sfc.compileTemplate({ ...templateOptions, source: descriptor.template.content, filename })
    if (t.errors.length > 0) throw t.errors[0]
    out.push(t.code.replace(/\bexport function render\b/, 'function _sfc_render'), '_sfc_main.render = _sfc_render')
  }
  if (scoped) out.push(`_sfc_main.__scopeId = ${JSON.stringify(scopeId)}`)

  const css = []
  for (const style of descriptor.styles) {
    if (style.lang && style.lang !== 'css') throw new Error(`@blender-ui/vue: ${filename}: <style lang="${style.lang}"> is not supported, only CSS`)
    const r = sfc.compileStyle({ source: style.content, filename, id: scopeId, scoped: style.scoped })
    if (r.errors.length > 0) throw r.errors[0]
    css.push(r.code)
  }
  if (css.length > 0) {
    out.push("import { addStyle as _addStyle } from '@blender-ui/vue'", `_addStyle(${JSON.stringify(id)}, ${JSON.stringify(css.join('\n'))})`)
  }
  out.push('export default _sfc_main')

  let code = out.join('\n')
  if (typescript && !keepTypes) code = require('node:module').stripTypeScriptTypes(code)
  return { code, typescript }
}
