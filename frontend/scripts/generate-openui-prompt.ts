import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { flowPilotOpenUIPrompt } from '../src/components/assistant/openuiLibrary'

const __dirname = dirname(fileURLToPath(import.meta.url))
const targetPath = resolve(__dirname, '../../backend/app/openui/flowpilot_openui_prompt.txt')

mkdirSync(dirname(targetPath), { recursive: true })
writeFileSync(
  targetPath,
  [
    '# Generated from frontend/src/components/assistant/openuiLibrary.tsx',
    '# Regenerate with: npm run generate:openui-prompt',
    '',
    flowPilotOpenUIPrompt,
    '',
  ].join('\n'),
  'utf8',
)

console.log(`OpenUI prompt generated: ${targetPath}`)
