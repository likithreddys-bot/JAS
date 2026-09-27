# Excel (manual test)

JAS drives Excel through COM — the same interface Excel's own macros use — not by clicking the
ribbon. It is far faster and it cannot misclick.

**One rule that matters:** Windows only lets JAS drive an Excel **it opened itself**. If you
double-click a file yourself, JAS cannot reach it. So ask JAS to open the file.

---

## TEST X.1 — Open and look
1. Say: **"JAS, open the sales file in Excel."** (any .xlsx or .csv in your folders)
2. Then: **"What columns are in it?"**
3. Expect: Excel opens, and JAS names the actual column headers.

## TEST X.2 — Compact a column (the one that failed before)
1. Say: **"JAS, compact column A."**
2. Expect: column A snaps to fit its contents, in about a second. No clicking, no thinking pause.

## TEST X.3 — A formula
1. Say: **"JAS, join all the values in column A into one cell."**
2. Expect: a `TEXTJOIN` formula appears and evaluates.
3. Try also: **"total column D"**, **"count how many rows say South"**.

## TEST X.4 — Sort
1. Say: **"JAS, sort by amount, biggest first."**
2. Expect: the rows reorder, header row untouched.

## TEST X.5 — Pivot / categorise
1. Say: **"JAS, total the amount by region and category."**
2. Expect: a new sheet called *Pivot* with the totals and a grand total.

## TEST X.6 — Save
1. Say: **"JAS, save it."**

---

### What is verified
Run live on this machine on 24 Sep 2026, checking the sheet actually changed rather than trusting
the tool's own word:

- open ✓ · headers read ✓
- **compact column A: width 8.1 → 28.4** ✓
- **TEXTJOIN written and evaluated** ✓
- **sort: [1200, 800, 450, 1750, 300] → [1750, 1200, 800, 450, 300]** ✓
- **pivot: North 1750 + 800 = 2550, South 1500 + 450 = 1950, grand total 4500** ✓

### Safety
The workbook is copied into `data/backups` before JAS's first change of the session, because COM
changes bypass Excel's undo. If the copy fails you are told, rather than it failing silently.

### Known limits
- A file **you** opened by double-clicking is not reachable; ask JAS to open it.
- If Excel is showing a dialog, JAS says "Excel is busy" instead of hanging.
- Charts, conditional formatting and macros are not covered yet.
