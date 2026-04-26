# Anti-patterns

## Hard bans

Generated UI must not contain:

- `bg-white`
- `bg-black`
- `bg-gray-*`
- `bg-slate-*`
- `text-gray-*`
- `text-slate-*`
- `text-red-*`
- `text-green-*`
- `border-gray-*`
- `border-slate-*`
- `shadow-lg`
- `shadow-xl`
- arbitrary gradients: `from-*`, `to-*`, `via-*`
- naked card divs
- primitive token usage in components

## Conditional bans

Only use these with an explicit component contract:

- `rounded-full`
- `p-8`
- `p-10`
- `gap-10`
- `gap-12`

## Structural bans

- No page-level arbitrary gradients.
- No status color as decoration.
- No table outside ArchiveSurface / ArchiveTable.
- No second design system.
- No direct primitive token references like `var(--stone-*)`, `var(--green-*)`, or `var(--red-*)` in component code.
