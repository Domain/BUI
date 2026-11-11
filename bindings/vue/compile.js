// Single-file components (`.vue`) for BUI: compiled with Vue's own compiler (`vue/compiler-sfc`),
// one place for the Node.js hooks (register.js) and the Bun plugin (plugin.js).
//
// What differs from a web build: the template compiler is Vue's DOM one with two changes. `v-model`
// is compiled with the core transform (props `modelValue` / `onUpdate:modelValue`, which model.js
// handles) because the DOM's `vModelText` and friends need a browser, and static hoisting into
// HTML strings (`createStaticVNode`) is off because there is no HTML parser to insert it with.
// `<style>` blocks are compiled by Vue (scoped ones get `[data-v-xxxx]` selectors) and handed to
// `addStyle`, which adds them to each window once. Only HTML templates, JavaScript or TypeScript
// scripts and CSS styles compile; other languages and `src=` blocks are errors, not silent.
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

/** `module.stripTypeScriptTypes`, which Node.js still marks experimental: it is the one TypeScript
 *  tool Node.js ships, so its notice (printed once, on the first `lang="ts"` component) is
 *  dropped here, and only that one. It only removes types, as `node file.ts` does: enums,
 *  namespaces and parameter properties are errors (Bun compiles all of TypeScript). */
function stripTypes (code, filename) {
  const { stripTypeScriptTypes } = require('node:module')
  const emit = process.emitWarning
  process.emitWarning = (warning, ...rest) => {
    if (!String(warning).includes('stripTypeScriptTypes')) emit.call(process, warning, ...rest)
  }
  try {
    return stripTypeScriptTypes(code)
  } catch (err) {
    throw new Error(`@blender-ui/vue: ${filename}: ${err.message} (Node.js strips TypeScript types only; use a const object instead of an enum, or run on Bun)`, { cause: err })
  } finally {
    process.emitWarning = emit
  }
}

/** The languages this package compiles; anything else would be taken for plain JavaScript or HTML. */
function checkLanguages (descriptor, filename) {
  const fail = (what) => { throw new Error(`@blender-ui/vue: ${filename}: ${what} is not supported`) }
  const { template, script, scriptSetup } = descriptor
  if (template && template.lang && template.lang !== 'html') fail(`<template lang="${template.lang}">, only HTML`)
  for (const s of [script, scriptSetup]) {
    if (s && s.lang && !['js', 'jsx', 'ts', 'tsx'].includes(s.lang)) fail(`<script lang="${s.lang}">`)
  }
  for (const block of [template, script, scriptSetup, ...descriptor.styles]) {
    if (block && block.src) fail('a block with src="…" (put the code in the file)')
  }
  // `v-bind()` in a style is kept up to date with a MutationObserver and the document's style rules;
  // CSS modules need the build tool to hand `$style` over
  if (descriptor.cssVars.length > 0) fail('v-bind() in <style>')
  if (descriptor.styles.some((s) => s.module)) fail('<style module>')
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
  checkLanguages(descriptor, filename)
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
  if (typescript && !keepTypes) code = stripTypes(code, filename)
  return { code, typescript }
}
