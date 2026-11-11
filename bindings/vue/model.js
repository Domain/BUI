// `v-model` on elements. compile.js compiles it with Vue's core transform, which gives an element
// `modelValue` and `onUpdate:modelValue` props instead of a DOM directive (vModelText & co. need a
// browser's DOM). This file is what those two props do: show the value in the control, and report
// the control's changes back, as `<input v-model>` does on the web:
//
//   text, search, password ...   the `input` event, a string      (.trim and .number through modelModifiers)
//   number, range                the `input` event, a number
//   checkbox                     `change`: a boolean, or the array / Set the box is a member of
//   radio                        `change`: the radio's value
//   select, color                `change`: the value
//
// Blender's widgets (`<NumberSlider v-model="n">`, `<Checkbox>`, `<Dropdown>`) are such elements,
// and components: modifiers on them reach this file as `modelModifiers`.
//
// SPDX-License-Identifier: GPL-2.0-or-later

/** The control an element is, for v-model. */
function kind (el) {
  switch (el.localName) {
    case 'textarea': return 'text'
    case 'select': return 'select'
    case 'input': {
      const type = el.getAttribute('type') ?? 'text'
      if (type === 'checkbox' || type === 'radio' || type === 'color') return type
      return type === 'number' || type === 'range' ? 'number' : 'text'
    }
  }
  return null
}

const state = (el) => (el._model ??= { value: undefined, update: null, mods: null, listener: null })

/** Vue's loose number conversion: a number when the text is one. */
const toNumber = (s) => {
  const n = parseFloat(s)
  return Number.isNaN(n) ? s : n
}

const isMember = (group, value) => (Array.isArray(group) ? group.some((v) => String(v) === value) : group.has(value))

/** Show `value` in the control. */
export function setModelValue (el, value) {
  state(el).value = value
  switch (kind(el)) {
    case 'checkbox':
      el.checked = Array.isArray(value) || value instanceof Set ? isMember(value, el.value) : Boolean(value)
      break
    case 'radio':
      el.checked = String(value) === el.value
      break
    case null:
      break
    default: {
      const text = value == null ? '' : String(value)
      if (el.value !== text) el.value = text // not while it already shows it: the caret stays
    }
  }
}

/** `.trim`, `.number` (`modelModifiers` of a component, or of a widget). */
export function setModelModifiers (el, mods) {
  state(el).mods = mods
}

/** What the control reports now. */
function read (el, m) {
  switch (kind(el)) {
    case 'checkbox': {
      const group = m.value
      if (Array.isArray(group)) {
        const next = group.filter((v) => String(v) !== el.value)
        if (el.checked) next.push(el.value)
        return next
      }
      if (group instanceof Set) {
        const next = new Set(group)
        if (el.checked) next.add(el.value)
        else next.delete(el.value)
        return next
      }
      return el.checked
    }
    case 'number': return toNumber(el.value)
    case 'text': {
      let v = el.value
      if (m.mods?.trim) v = v.trim()
      return m.mods?.number ? toNumber(v) : v
    }
    default: return el.value
  }
}

/** Report changes of the control to `update` (the handler of `onUpdate:modelValue`), or stop. */
export function setModelUpdate (el, update) {
  const m = state(el)
  m.update = update
  if (update == null || m.listener !== null) return
  const k = kind(el)
  if (k === null) return
  m.listener = () => m.update?.(read(el, m)) // the latest handler: a re-render may have replaced it
  el.addEventListener(k === 'text' || k === 'number' ? 'input' : 'change', m.listener)
}
