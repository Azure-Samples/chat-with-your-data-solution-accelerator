---
title: CWYD v2 — Worklog
description: Convention for the CWYD v2 daily worklog. One dated file per working day captures the plan, completed work, bugs found and fixed, decisions, and next steps.
author: CWYD Engineering
ms.date: 2026-06-10
topic: reference
keywords: worklog, daily log, convention, recovery, v2
estimated_reading_time: 3
---

## What this folder is

A durable, file-based record of daily work on CWYD v2. Each working day has one file named by ISO date: `YYYY-MM-DD.md`. Plans and progress live here, not in ephemeral agent memory.

This complements two neighbors:

* [bugs.md](../bugs.md) is the canonical defect registry. Bugs are recorded there and cross-referenced from the day's worklog.
* [development_plan.md](../development_plan.md) holds phase ordering and the §0.1 and §0.2 phase debt queues.

## When to create a file

Create `YYYY-MM-DD.md` on the first meaningful action of each working day, using the real current date. Verify the date before naming the file. Append to the same file as the day progresses rather than opening a second file for the same date.

## Sections

Each daily file starts with the standard frontmatter (`title`, `description`, `author`, `ms.date`, `topic`, `keywords`, `estimated_reading_time`) and then uses these sections:

* Summary: one or two sentences on the day's focus.
* Planned: what the day set out to do.
* Done: what was completed, with links to the files or docs touched.
* Bugs: defects found or fixed, each linking its `BUG-####` entry in [bugs.md](../bugs.md).
* Decisions: choices made and their rationale.
* Next: what comes next.

## Placeholder rule

Worklog files are tracked. Never write real environment values. Use the placeholder tokens defined in [adr/0019-no-env-specific-content-in-tracked-files.md](../adr/0019-no-env-specific-content-in-tracked-files.md).
