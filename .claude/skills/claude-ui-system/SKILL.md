---
name: claude-ui-system
description: Generate and review Fund Screener pages using the Claude-like archive finance UI contract.
---

# Claude UI System

Every page generation starts by selecting one archetype before writing JSX.

## Required flow

1. Select exactly one page archetype from `patterns/page-archetypes.md`.
2. Map the page content into conclusion/status, key metrics, evidence data, and action.
3. Compose with `PageShell`, `PageHeader`, `Surface`, `ArchiveTable`, `MetricValue`, and `SignalBadge` where applicable.
4. Check `anti-patterns.md` before returning code.
5. Run the checklist in `checklist.md` before claiming the page is done.

## Direction

The UI should feel like a Claude-written fund research archive: warm Stone surfaces, low contrast, restrained motion, dense evidence tables, and semantic financial color only for status or evidence.
