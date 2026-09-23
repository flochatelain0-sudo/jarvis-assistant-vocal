// Copie le build inline (dist/index.html) vers ../web/console.html.
// Le HTML produit est autonome : JS et CSS inlines, aucune ressource externe.
import { copyFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ici = dirname(fileURLToPath(import.meta.url))
const source = resolve(ici, '..', 'dist', 'index.html')
const cible = resolve(ici, '..', '..', 'web', 'console.html')
copyFileSync(source, cible)
console.log('web/console.html mis a jour depuis console-ui/dist/index.html')
