# Welcome to MARS!

Hi, and welcome! I built MARS because I kept watching us (myself included) burn
days on research directions that a little upfront scrutiny would've flagged as
dead ends — and miss sharper angles sitting right next to the obvious one. A
single chatbot wasn't much help here; it's too eager to agree and make everything
sound promising.

So MARS is the opposite of that. You hand it a question, your papers, and your
data, and a team of AI agents goes to work: reading the literature, *actually
running statistics on your dataset*, arguing with each other, and trying hard to
kill weak ideas. What you get back is a short, ranked list of directions worth
pursuing, the ones that are probably traps (with the reasoning spelled out), and
a receipt for every claim it makes. It's meant to tell you the truth, not flatter
you.

It's a website — no setup, no code. Just open it and go. Here's how.

---

## How to use it

1. **Open the app:** http://10.250.9.34:8501
   *(That's on the lab network. If it won't load, ping me — the address can change.)*

2. **Ask a real question.** The more specific, the better the answer.
   - Like this: *"Does time pressure reduce idea diversity in collaborative ideation?"*
   - Not this: *"time pressure and ideas"*

3. **Upload what you've got.** Papers as PDFs, data as CSV or Excel.

4. **Add your initials** so we know who ran it (no password, don't worry).

5. **Pick how you want ideas ranked:** Balanced, Novelty-seeking, or
   Feasibility-first. Same evidence, different priorities — feel free to try a
   couple and compare.

6. **Hit Run** and give it a few minutes. You'll see each agent working as it goes.

When it's done, you can read the report on screen and download it as Markdown or
PDF. The full evidence file is there too, if you want to dig in.

---

## What you'll see in the results

- **Endorsed** — the directions that held up. Start here.
- **Contested** — promising, but something's shaky. I'd read the "why" before
  committing.
- **Likely dead-end** — MARS thinks this is a trap, and shows you the evidence
  for that call.
- **Confidence (High / Medium / Low)** — this is *computed* from the evidence,
  not the model's mood.
- **Evidence drill-down** — every claim, where it came from, who backed it up,
  and who pushed back.

One thing that surprises people: MARS endorses *fewer* directions than it comes
up with. That's on purpose. A short list you can defend beats a long list you
can't.

---

## How it works (the short version)

It's a team of specialists that argue and then loop until the evidence is solid:

- **Literature** reads your papers and maps the gaps.
- **Scout** goes looking for related work you didn't upload.
- **Data Explorer** writes and runs real analysis on your data — and logs *every*
  test it tries, including the ones that found nothing.
- **Hypothesis** turns gaps and data into testable directions.
- **Methods** checks whether your data can actually carry each one.
- **Critique** can block a weak idea from looking strong.
- **Red-team** tries to kill your best idea and pitch a better one.

Everything they say is recorded as evidence, confidence is calculated from how
well each claim is grounded and independently backed, and an editor loops the
team for another round if things aren't tight yet. The full write-up is on GitHub
if you're curious.

---

## A few tips

- Sharper question, sharper answer. Name the variables and the population.
- Give it real data — the Data Explorer is where a lot of the magic happens.
- Try different ranking presets on the same inputs and see what shifts.
- Don't just trust it — open the drill-down. Every number traces back to a
  re-runnable analysis you can check.

---

## Hosting it yourself (only if you're running the machine)

Most people can ignore this. If you're the one hosting MARS for the lab:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add the lab Claude key: ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Then share `http://<machine-ip>:8501` with everyone. The README has the full
setup and the honest notes on what MARS does and doesn't guarantee.

---

## Stuck, or have an idea?

Reach out anytime — I'm happy to help and always up for feedback.

**Vishnu Kulkarni — vikulkarni@hbs.edu**
More docs and the code: **https://github.com/vishnuskulkarni/mars-v2**

Happy researching.
