// The Bun plugin: `.vue` files. `bui build` finds the default export through this package's
// `"bui": { "bunPlugin" }` field and bundles with it; Bun's runtime loads it through register.js.
//
// SPDX-License-Identifier: GPL-2.0-or-later
import fs from 'node:fs'
import { VUE_FILE, SELF, selfFile, compileVue } from './compile.js'

export default {
  name: '@blender-ui/vue',
  setup (build) {
    build.onResolve({ filter: SELF }, () => ({ path: selfFile() }))
    build.onLoad({ filter: VUE_FILE }, (args) => {
      // Bun transpiles TypeScript itself
      const { code, typescript } = compileVue(fs.readFileSync(args.path, 'utf8'), args.path, { keepTypes: true })
      return { contents: code, loader: typescript ? 'ts' : 'js' }
    })
  },
}
