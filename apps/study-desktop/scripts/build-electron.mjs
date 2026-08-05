import { build } from 'esbuild'
import { mkdirSync } from 'node:fs'

mkdirSync('dist-electron', { recursive: true })

await build({
  entryPoints: ['electron/main.ts'],
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node22',
  outfile: 'dist-electron/main.js',
  external: ['electron'],
})

await build({
  entryPoints: ['electron/preload.ts'],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  target: 'node22',
  outfile: 'dist-electron/preload.cjs',
  external: ['electron'],
})

console.log('✓ built dist-electron/main.js (esm) and dist-electron/preload.cjs (cjs)')
