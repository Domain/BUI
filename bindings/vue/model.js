// `v-model` on elements. compile.js compiles it with Vue's core transform, which gives an element
// `modelValue` and `onUpdate:modelValue` props instead of a DOM directive (vModelText & co. need a
// browser's DOM). This file is what those two props do: show the value in the control, and report
// the control's changes back, as `<input v-model>` does on the web:
//
//   text, search, password ...   the `input` event, a string      (.trim and .number through modelModifiers)
//   number, range                the `input` event, a number
//   checkbox                     `change`: a boolean (or `true-value` / `false-value`), or the array / Set
//                                the box is a member of
//   radio                        `change`: the radio's value (the bound value, a number stays a number)
//   select, color                `change`: the value
//
// Blender's widgets (`<NumberSlider v-model="n">`, `<Checkbox>`, `<Dropdown>`) are such elements,
// and components: modifiers on them reach this file as `modelModifiers`.
//
// SPDX-License-Identifier: GPL-2.0-or-later
import { callWithAsyncErrorHandling, ErrorCodes } from 'vue'

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

const state = (el) => (el._model ??= { value: undefined, update: null, instance: null, mods: null, listener: null })

/** Vue's loose number conversion: a number when the text is one. */
const toNumber = (s) => {
  const n = parseFloat(s)
  return Number.isNaN(n) ? s : n
}

/** The value a checkbox or radio stands for: what `:value` was bound to (a number, an object), else
 *  its `value` attribute. `props.js` keeps the bound one in `_value`, as Vue's DOM renderer does. */
const valueOf = (el) => ('_value' in el ? el._value : el.value)

/** Vue's `looseEqual` for what a control can hold: primitives by their text, objects by identity. */
const same = (a, b) => (Object(a) === a || Object(b) === b ? a === b : String(a) === String(b))

const trueValue = (el) => ('_trueValue' in el ? el._trueValue : true)
const falseValue = (el) => ('_falseValue' in el ? el._falseValue : false)

/** Show `value` in the control. */
export function setModelValue (el, value) {
  state(el).value = value
  switch (kind(el)) {
    case 'checkbox':
      if (Array.isArray(value)) el.checked = value.some((v) => same(v, valueOf(el)))
      else if (value instanceof Set) el.checked = value.has(valueOf(el))
      else el.checked = same(value, trueValue(el))
      break
    case 'radio':
      el.checked = same(value, valueOf(el))
      break
    case null:
      break
    default: {
      const text = value == null ? '' : String(value)
      if (el.value !== text) el.value = text // not while it already shows it: the caret stays
    }
  }
}

/** Show the model's value again: `value`, `true-value` and `false-value` arrive after `modelValue`
 *  (Vue patches `value` last), and a checkbox or a radio compares with them. */
export function refreshModel (el) {
  if (el._model != null) setModelValue(el, el._model.value)
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
      const v = valueOf(el)
      if (Array.isArray(group)) {
        const next = group.filter((x) => !same(x, v))
        if (el.checked) next.push(v)
        return next
      }
      if (group instanceof Set) {
        const next = new Set(group)
        if (el.checked) next.add(v)
        else next.delete(v)
        return next
      }
      return el.checked ? trueValue(el) : falseValue(el)
    }
    case 'radio': return valueOf(el)
    case 'number': return toNumber(el.value)
    case 'text': {
      let v = el.value
      if (m.mods?.trim) v = v.trim()
      return m.mods?.number ? toNumber(v) : v
    }
    default: return el.value
  }
}

/** Report changes of the control to `update` (the handler of `onUpdate:modelValue`), or stop. Its
 *  errors go through Vue's handlers, for `instance` (the component whose template has the control). */
export function setModelUpdate (el, update, instance) {
  const m = state(el)
  m.update = update
  m.instance = instance
  if (update == null || m.listener !== null) return
  const k = kind(el)
  if (k === null) return
  m.listener = () => { // the latest handler: a re-render may have replaced it
    if (m.update != null) callWithAsyncErrorHandling(m.update, m.instance, ErrorCodes.NATIVE_EVENT_HANDLER, [read(el, m)])
  }
  el.addEventListener(k === 'text' || k === 'number' ? 'input' : 'change', m.listener)
}
