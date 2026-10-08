"""Run the 35 test questions through both designs and score them.

  py evaluate.py                 # both designs, all questions (about $2)
  py evaluate.py --limit 5       # quick check on the first 5 questions
  py evaluate.py --design B      # one design only

Each answer is graded against the reference answer by a separate Claude call
("LLM as judge"), and its citations are checked against the page the answer is on.
Results are saved to results/eval-<time>.csv.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from assistant import ROOT, FullContextAssistant, SearchAssistant, _Base

RESULTS = ROOT / "results"

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["correct", "partially_correct", "incorrect"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}

JUDGE_PROMPT = """You are grading an assistant that answers staff questions using company documents.

Question: {question}
Reference answer: {reference}
Assistant's answer: {answer}

Grade the assistant's answer:
- correct: it states the key facts of the reference answer and nothing that contradicts it. Extra accurate detail is fine.
- partially_correct: it gets the main point right but misses or muddles an important detail from the reference.
- incorrect: it is wrong, contradicts the reference, presents an outdated rule as the current one, or invents information.
If the reference answer is "Not in the documents.", the answer is correct only if the assistant says it could not find the information and does not invent an answer.
Give a one-sentence reason."""


class Judge(_Base):
    approach = "judge"

    def grade(self, question: str, reference: str, answer: str) -> dict:
        response = self.client.beta.messages.create(
            model="claude-opus-5-5",
            max_tokens=2000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
            messages=[{"role": "user", "content": JUDGE_PROMPT.format(question=question, reference=reference, answer=answer)}],
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
        text = next(b.text for b in response.content if b.type == "text")
        usage = response.usage
        return {**json.loads(text), "judge_cost": (usage.input_tokens * 4 + usage.output_tokens * 20) / 1e6}


def expected_pages(questions: list[dict]) -> dict:
    """The page each answer is on, found by searching the PDF for the anchor phrase."""
    pages, cache = {}, {}
    for q in questions:
        if not q["source_doc"]:
            continue
        doc = q["source_doc"]
        cache.setdefault(doc, [" ".join(p.extract_text().split()) for p in PdfReader(ROOT / "documents" / f"{doc}.pdf").pages])
        pages[q["id"]] = next(i + 1 for i, text in enumerate(cache[doc]) if q["anchor"] in text)
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--design", choices=["A", "B", "both"], default="both")
    args = parser.parse_args()

    questions = json.load(open(ROOT / "questions.json", encoding="utf-8"))[: args.limit]
    pages = expected_pages(questions)
    designs = {"A": FullContextAssistant, "B": SearchAssistant}
    chosen = ["A", "B"] if args.design == "both" else [args.design]
    judge = Judge()

    rows = []
    for key in chosen:
        assistant = designs[key]()
        print(f"\n=== Design {assistant.approach} ===")
        for q in questions:
            a = assistant.ask(q["question"])
            g = judge.grade(q["question"], q["reference_answer"], a.text)
            cited = {(c.doc, c.page) for c in a.citations}
            citation_ok = None if not q["source_doc"] else (q["source_doc"], pages[q["id"]]) in cited
            rows.append({
                "design": key, "id": q["id"], "category": q["category"], "question": q["question"],
                "verdict": g["verdict"], "citation_ok": citation_ok, "seconds": round(a.seconds, 2),
                "cost": round(a.cost, 5), "judge_cost": round(g["judge_cost"], 5),
                "answer": a.text, "citations": "; ".join(f"{c.doc} p.{c.page}" for c in a.citations),
                "judge_reason": g["reason"], "passages": "; ".join(a.passages),
            })
            mark = {"correct": "OK  ", "partially_correct": "PART", "incorrect": "FAIL"}[g["verdict"]]
            print(f"  {mark} Q{q['id']:>2} {q['question'][:60]:<60} {a.seconds:4.1f}s ${a.cost:.4f}")

    df = pd.DataFrame(rows)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"eval-{datetime.now():%Y%m%d-%H%M%S}.csv"
    df.to_csv(out, index=False, encoding="utf-8")

    print("\n=== Summary ===")
    for key, d in df.groupby("design"):
        answerable = d[d["citation_ok"].notna()]
        print(f"\nDesign {key}:")
        print(f"  Correct:            {(d.verdict == 'correct').sum()} / {len(d)}   (partly correct: {(d.verdict == 'partially_correct').sum()}, incorrect: {(d.verdict == 'incorrect').sum()})")
        print(f"  Citation on the right page: {int(answerable.citation_ok.sum())} / {len(answerable)}")
        print(f"  Avg time per question:      {d.seconds.mean():.1f} s")
        print(f"  Avg cost per question:      ${d.cost.mean():.4f}   (total ${d.cost.sum():.2f})")
        by_cat = d.groupby("category").apply(lambda g: f"{(g.verdict == 'correct').sum()}/{len(g)}", include_groups=False)
        print("  By category:        " + ", ".join(f"{c} {v}" for c, v in by_cat.items()))
    print(f"\nJudge cost: ${df.judge_cost.sum():.2f}   Results: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
