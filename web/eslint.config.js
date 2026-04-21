import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // DSGN-08: 禁止硬编码 Tailwind 颜色类，强制使用语义 Token
      'no-restricted-syntax': [
        'error',
        {
          selector:
            'Literal[value=/\\b(bg|text|border)-(white|black|gray-[0-9]+|slate-[0-9]+|zinc-[0-9]+|neutral-[0-9]+|stone-[0-9]+|red-[0-9]+|orange-[0-9]+|amber-[0-9]+|yellow-[0-9]+|lime-[0-9]+|green-[0-9]+|emerald-[0-9]+|teal-[0-9]+|cyan-[0-9]+|sky-[0-9]+|blue-[0-9]+|indigo-[0-9]+|violet-[0-9]+|purple-[0-9]+|fuchsia-[0-9]+|pink-[0-9]+|rose-[0-9]+)/]',
          message:
            '禁止使用硬编码 Tailwind 颜色类（如 bg-white、text-gray-500）。请使用语义 Token：var(--text-primary)、var(--bg-surface)、var(--accent-success) 等。详见 tokens.semantic.css',
        },
      ],
    },
  },
])
