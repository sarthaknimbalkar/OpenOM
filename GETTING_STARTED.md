# Getting started (for brokers)

**You have an offering memorandum (OM) PDF and you want it to carry your deal data
inside it, so a buyer, a portal, or an AI tool can read the deal instantly and see it
came from you, unchanged.** This guide walks you through the whole thing.

**You do not need to be technical.** You will never open a terminal, never write code,
and never create a "deal.json" file. If you tried the command line before and hit
confusing errors about a missing `deal.json` - that path was never meant for you. This
guide uses the browser instead.

> **The 10-second summary**
>
> 1. Go to **<https://openom.app/embed/>** (nothing to install), or install the Chrome
>    extension.
> 2. Open your OM PDF, fill in a short review form (your name is remembered), and click
>    **Assert & Embed**.
> 3. A new copy of the PDF downloads. It looks identical - but now it carries your
>    verified deal data.
>
> Your PDF never leaves your computer. Everything happens in your browser.

---

## First, two things worth knowing

**"Verified" means *who said it and that it hasn't been changed* - not that it's
"true."** An OM is your professional opinion of value, as of a date. openOM records
**who** asserted the numbers, that the file is **unaltered since**, and **as of when** -
it never claims your numbers are market fact. That's the whole point: it's your
assertion, clearly attributed to you.

**Your numbers are your assertion.** Nothing here checks your deal against the market.
The tool only checks that your entries are internally consistent (for example, that
NOI ÷ price roughly matches the cap rate you typed) and flags anything that looks off.
Those flags are just heads-ups - see [Errors vs. warnings](#step-6-understand-errors-vs-warnings)
below.

---

## What you'll need

- **Google Chrome** (version 116 or newer), or Microsoft Edge. That's it.
- **Your OM PDF** on your computer, or open in a browser tab.
- **Your broker details** the first time: your name, your brokerage, and your license
  number. You enter these **once** and they're saved on your computer for next time.

You do **not** need: a terminal, Python, "npm", any file called `deal.json`, an account,
or an internet connection that uploads your file. (The file stays on your machine.)

---

## Choose your door

There are two no-terminal ways in. Both do the same job.

| Option | Best when | How |
|--------|-----------|-----|
| **A. The web tool** (recommended to start) | You just want to embed one OM with nothing to install. | Go to **<https://openom.app/embed/>** |
| **B. The Chrome extension** | You do this regularly and want a button in your browser, plus verify badges on OMs you come across. | Install once (see below) |

Everything below describes the extension's flow, because it's the fuller experience -
but the web tool at openom.app/embed/ walks you through the **same review form and the
same buttons**, so you can follow along there too.

---

## Installing the Chrome extension (optional - Option B)

The extension is on the Chrome Web Store - **one-click install, and it auto-updates:**
**<https://chromewebstore.google.com/detail/openom/koconccgjacmafhabbiakodicffnaplb>**

Prefer not to install anything? A broker can always just **use the web tool at
<https://openom.app/embed/> instead** - same review-and-embed flow, no install at all.

Once installed, click the openOM icon in your Chrome toolbar. Author mode (the embedding
flow) opens from the popup's **"Embed a payload…"** button, which opens a side panel.

---

## The full journey, step by step

### Step 1 - Open your OM

**What you do:** Start the embed flow (open <https://openom.app/embed/>, or click
**"Embed a payload…"** in the extension). You'll see a screen titled **"embed a
payload"** with two choices:

- **Use current tab's PDF** - if the OM is already open in a browser tab.
- **A file picker** - to choose the OM PDF from your computer.

**What you'll see:** After you pick the OM, a short "Fetching PDF…" message, then the
review workspace opens.

> **If your OM is a Buildout listing:** if you're on a Buildout listing tab and Buildout
> has been connected for you, you'll see a note that the deal's fields will be
> **imported from Buildout automatically** once you choose the OM PDF. That's the most
> accurate path when it's available.

**A few OMs get a plain-language heads-up here instead of the form:**

- **Encrypted OM** - "This OM is encrypted - the browser extension can't embed into it."
  Ask the sender for an unencrypted copy, or have a technical colleague use the command
  line (which handles encrypted OMs). This is not an error you did - some PDFs are locked.
- **Digitally signed OM** - embedding rewrites the file and would break the existing
  signature. You'll be asked to tick a box acknowledging that before you can continue.
  (To keep the signature intact, the command-line tool is the path.)
- **Scanned OM (no text layer)** - you can still fill the form by hand; the optional AI
  draft (Step 3) just can't read a scan.

---

### Step 2 - Enter your broker details (once)

**What you do:** Under **"Reviewing broker,"** fill in three fields:

- **broker** - your name
- **brokerage** - your firm
- **license** - your license number

**What you'll see:** These fields come **pre-filled** on every OM after the first time,
because they're **saved on your computer**. This solves the "why do I have to retype my
name every deal?" annoyance - you don't. They are stored **only on this device** and are
never synced or uploaded anywhere.

> All three are required to finish (they become the "asserted by" record that says the
> deal data is *yours*). If any is blank, the tool will remind you before you can assert.

---

### Step 3 - (Optional) Let on-device AI draft the fields for you

This step is **completely optional.** **Typing the fields in by hand is the normal,
fully supported way to do this** - the AI is only a convenience that pre-fills a draft
you then review.

**What you'll see, depending on your computer:**

- **A "Extract with on-device AI" button** - click it and the tool reads the OM's text
  and pre-fills the review form with suggested values, each linked to the page it came
  from.
- **A "Download on-device AI (~1–2 GB), then extract" button** - the AI model isn't
  downloaded yet. Clicking it downloads it first (you'll see progress right under the
  button). This is a one-time, large download. You can skip it entirely and type the
  fields yourself.
- **"On-device AI unavailable - enter fields manually."** - your Chrome version or
  computer doesn't offer the built-in AI. This is normal and fine. **Just fill the form
  by hand.**

**Why this happens (the "I thought it would use Chrome AI but no?" question):** the AI
runs *entirely on your computer* using Chrome's built-in AI feature. It requires a recent
Chrome and a machine that supports it, and the model must be downloaded (that 1–2 GB).
Not every computer qualifies - and that's okay, because the AI is never required to
finish. It only ever writes a **draft you must review and approve.** Confidence from a
model is not your consent - *you* are the one who asserts, in Step 5.

Whatever route you take, after extraction you'll see: **"Extracted a draft - review every
field before asserting."**

---

### Step 4 - Review and correct the deal fields

**What you do:** Go through the form and check every value. Fill anything missing.

**What you'll see:**

- **An "Omitted (confirm or supply)" list** - fields the standard knows about that you
  haven't filled. These are prompts, not errors; supply them if you have them.
- **A live "Will be embedded" recap** - a plain-English summary of what you're about to
  assert (Property, Asking price, Cap rate, NOI, Tenant, Asserted by, Asserted date).
  Read this - it's the human-friendly version of the data. (An expandable "Show the exact
  JSON" is there too if you're curious, but you never have to touch it.)

> **⚠️ The one trap to know about: the cap rate.**
>
> Enter the cap rate as a **decimal**, not a percent. A 6.25% cap rate is **`0.0625`**,
> not `6.25`. Same idea for any other percentage-style field.
>
> If you type `6.25`, you'll get an error saying the value is above the maximum of 1 -
> that's the tool telling you it expected a decimal fraction. Change `6.25` to `0.0625`
> and it clears.

> **If you enter an NOI**, you'll also be asked for two related things: whether it's
> **in-place** or **pro-forma**, and its **as-of date**. This is required so a reader
> knows exactly what your NOI means. If you skip them you'll see an error like
> "noiType/noiAsOfDate required with noi" - just pick the type and date and it clears.

---

### Step 5 - Assert & embed

**What you do:** When the form is clean (no red errors - see next step), click
**"Assert & Embed."**

**What you'll see:**

- The button is **greyed out until there are no errors.** Warnings do **not** grey it
  out (again, see the next step).
- When you click it, the tool stamps the deal data with **your identity** ("asserted by")
  and **today's date** ("asserted date"), writes it inside a fresh copy of the PDF, and
  the file **downloads automatically**.
- Status message: **"Embedded - downloaded the OM."**

**The downloaded PDF looks exactly like the original** - same pages, same layout,
same everything a person sees. The deal data rides along invisibly inside it.

> **Re-doing a deal later (reprice)?** If you open a PDF that already has your openOM data
> and change the numbers, you'll see a **"Reprice - you are approving a change"** panel
> showing exactly what changed (old → new). The new version **replaces** the old one and
> records that it supersedes it - your data never "stacks up" inside the file.

---

### Step 6 - Understand errors vs. warnings

This is the "none of my OMs worked, all validation errors" confusion, cleared up:

- **Errors (red, "must fix before asserting")** - these **block** the Assert button.
  They mean a value doesn't fit the required shape - for example, a cap rate typed as a
  percent instead of a decimal, a date in the wrong format, or an NOI without its type
  and as-of date. Each error tells you the field. Fix the value and the error disappears.
  (You may see a short code like `OMV-E001` in parentheses - that's just an internal
  label; the words before it tell you what to do.)

- **Warnings (yellow, "residual warnings")** - these **never block you.** A warning is a
  polite double-check, most often about internal consistency - for example, if your NOI ÷
  asking price doesn't quite line up with the cap rate you entered. You're allowed to
  assert anyway (sometimes the numbers legitimately don't tie out). Read them, and if
  they surprise you, re-check the value; if they're expected, proceed.

**In short: fix the red, glance at the yellow, then assert.**

---

### Step 7 - Verify the file (prove it worked)

**What you do:** Open **<https://openom.app/verify/>** and drop in the PDF you just
downloaded. (If you have the extension, its toolbar popup also shows a badge on any
openOM PDF you open.)

**What you'll see:** confirmation that the file contains openOM data, that it's
**unaltered since you embedded it**, and a readout of the deal - including your name as
the asserting broker and the date. That "unaltered, asserted by you" status is exactly
what a buyer or portal will see too.

Want a working example to try verifying first? Download the
[sample OM](https://openom.app/sample/openom-sample.pdf) and drop it into the verifier.

---

## Quick answers to common worries

**"Does my OM get uploaded somewhere?"**
No. Both the web tool and the extension work entirely in your browser. The file's bytes
never leave your computer.

**"Do I need to make a `deal.json` file or use the terminal?"**
No. That's the developer path. In the browser, the review form *is* the deal data - you
just fill it in. There's nothing to create beforehand.

**"Do I have to retype my name every time?"**
No. Your broker profile (name, brokerage, license) is saved on your device after the
first OM and pre-fills automatically thereafter.

**"Do I need the Chrome AI?"**
No. It's an optional convenience that drafts fields for you. Typing them in by hand is
the normal, fully-supported way, and many computers won't offer the AI at all.

**"It said 'validation errors' and I got stuck."**
Look for the **red "Errors (must fix)"** section - it names the exact field. The usual
culprit is a **cap rate typed as `6.25` instead of `0.0625`**, or an **NOI missing its
in-place/pro-forma type and as-of date.** Fix those and Assert lights up. Yellow
warnings don't block you.

**"My OM won't open - it's encrypted."**
Some PDFs are locked. Ask the sender for an unencrypted copy, or have a technical
colleague run the command-line tool, which handles encrypted OMs.

---

## If you prefer the command line (rare, for technical brokers)

Most brokers should stop here - the browser is the intended path. But if you're
comfortable in a terminal and have Python, from a checkout of the project you can do the
same thing with the `om` command:

```bash
pip install -e core -e cli

# Start from a ready-made sample payload instead of writing one from scratch,
# then edit the values to match your deal:
cp spec/samples/valid-stnl.json deal.json

om embed offering.pdf --payload deal.json --out out.pdf \
  --asserted-date 2026-08-24 --validate
om read out.pdf          # confirm the data round-trips
om validate deal.json    # the 0.1 schema is bundled - no --schema needed
```

The `--validate` flag makes `embed` refuse if there are schema errors (the same errors
the browser form shows). The cap-rate-as-decimal and NOI-type rules apply here too. Full
developer docs are at <https://openom.app/docs/> and in [`examples/`](examples/).
