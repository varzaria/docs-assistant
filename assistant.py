"""'Ask our documents' assistant: answers questions from company PDFs, with page citations.

Two designs, so they can be compared:
  FullContextAssistant  sends every document with every question (cached after the first call)
  SearchAssistant       finds the most relevant passages with keyword search and sends only those

Two document sets:
  cafe  the Kildare Craft Coffee staff documents (10 pages)
  esg   three public Irish sustainability reports (467 pages; run download_esg_reports.py first)

Both designs use Claude's built-in citations, so every statement links to a document and page.
"""

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).parent
MODEL = "claude-opus-5-5"
EFFORT = "medium"
PRICES = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}  # USD per million tokens

CAFE_PROMPT = """You answer questions from staff at Kildare Craft Coffee Ltd, using only the company documents provided.

- Base every statement on the documents and cite them. Do not add outside knowledge or assumptions.
- If the documents do not answer the question, say clearly that you could not find it in the company documents and suggest asking the café manager. Do not guess.
- Some documents are updated by later ones, such as a memo. If documents disagree, give the most recent rule, say when it changed, and mention what it replaced.
- Answer in one to four short sentences or a short list, in plain English, as if replying to a colleague."""

ESG_PROMPT = """You answer questions about companies' sustainability and annual reports, using only the reports provided.

- Base every statement on the reports and cite them. Do not add outside knowledge or assumptions.
- Give figures with their units and the year or period they refer to.
- If the reports do not answer the question, say clearly that you could not find it in the reports provided. Do not guess, and do not fill gaps with general knowledge about the company.
- Answer in one to four short sentences or a short list, in plain English."""

DOC_SETS = {
    "cafe": {"folder": ROOT / "documents", "prompt": CAFE_PROMPT},
    "esg": {"folder": ROOT / "esg_reports", "prompt": ESG_PROMPT},
}


@dataclass
class Citation:
    doc: str
    page: int
    quote: str


@dataclass
class Answer:
    text: str
    citations: list[Citation]
    approach: str
    seconds: float
    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    passages: list[str] = field(default_factory=list)  # what the search design retrieved

    @property
    def cost(self) -> float:
        return (self.input_tokens * PRICES["input"] + self.output_tokens * PRICES["output"]
                + self.cache_read_tokens * PRICES["cache_read"] + self.cache_write_tokens * PRICES["cache_write"]) / 1e6


def load_documents(folder: Path) -> list[dict]:
    """Read each PDF's text page by page. The text is saved to a cache file next to the PDFs,
    because extracting hundreds of pages takes minutes; the cache is refreshed if a PDF changes."""
    cache_path = folder / ".text_cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    docs, changed = [], False
    for path in sorted(folder.glob("*.pdf")):
        stamp = f"{path.stat().st_size}-{path.stat().st_mtime_ns}"
        entry = cache.get(path.name)
        if not entry or entry["stamp"] != stamp:
            pages = [" ".join((p.extract_text() or "").split()) for p in PdfReader(path).pages]
            cache[path.name] = entry = {"stamp": stamp, "pages": pages}
            changed = True
        docs.append({"name": path.stem, "path": path, "pages": entry["pages"]})
    if changed and folder.exists():
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return docs


class _Base:
    approach = ""

    def __init__(self, doc_set: str = "cafe"):
        load_dotenv(ROOT / ".env")
        self.client = anthropic.Anthropic()
        self.doc_set = doc_set
        self.system_prompt = DOC_SETS[doc_set]["prompt"]
        self.docs = load_documents(DOC_SETS[doc_set]["folder"])
        if not self.docs:
            raise FileNotFoundError(f"No PDFs in {DOC_SETS[doc_set]['folder']}")

    def _call(self, content: list[dict]):
        return self.client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=self.system_prompt,
            output_config={"effort": EFFORT},
            messages=[{"role": "user", "content": content}],
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},  # if a request is declined, retry on Anthropic's recommended model
        )

    def _to_answer(self, response, started: float, locate) -> Answer:
        """Join the text blocks, number each cited source [1], [2]... and record usage."""
        if response.stop_reason == "refusal":
            return Answer("Sorry, I can't answer that one.", [], self.approach, time.time() - started)
        text, citations, numbers = "", [], {}
        for block in response.content:
            if block.type != "text":
                continue
            text += block.text
            marks = []
            for c in block.citations or []:
                doc, page = locate(c)
                if (doc, page) not in numbers:
                    numbers[(doc, page)] = len(numbers) + 1
                    citations.append(Citation(doc, page, c.cited_text.strip()))
                if f"[{numbers[(doc, page)]}]" not in marks:
                    marks.append(f"[{numbers[(doc, page)]}]")
            if marks:
                text += " " + "".join(marks)
        u = response.usage
        return Answer(
            text=text.strip(), citations=citations, approach=self.approach, seconds=time.time() - started,
            input_tokens=u.input_tokens, output_tokens=u.output_tokens,
            cache_read_tokens=u.cache_read_input_tokens or 0, cache_write_tokens=u.cache_creation_input_tokens or 0,
        )


class FullContextAssistant(_Base):
    """Design A: every document goes to Claude with every question.

    Small sets are sent as PDFs (Claude sees each page as text and as an image).
    Large sets are sent as plain text, one block per page: page images for
    hundreds of pages would cost roughly three times as many tokens.
    """

    approach = "A: read everything"

    def __init__(self, doc_set: str = "cafe", as_text: bool | None = None):
        super().__init__(doc_set)
        self.as_text = (doc_set == "esg") if as_text is None else as_text
        self.blocks = [self._text_block(d) if self.as_text else self._pdf_block(d) for d in self.docs]
        self.blocks[-1]["cache_control"] = {"type": "ephemeral"}  # cache all documents after the first question

    @staticmethod
    def _pdf_block(doc: dict) -> dict:
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf",
                       "data": base64.standard_b64encode(doc["path"].read_bytes()).decode()},
            "title": f"{doc['name']}.pdf",
            "citations": {"enabled": True},
        }

    @staticmethod
    def _text_block(doc: dict) -> dict:
        return {
            "type": "document",
            "source": {"type": "content", "content": [{"type": "text", "text": page or "(blank page)"} for page in doc["pages"]]},
            "title": f"{doc['name']}.pdf",
            "citations": {"enabled": True},
        }

    def ask(self, question: str) -> Answer:
        started = time.time()
        response = self._call(self.blocks + [{"type": "text", "text": question}])

        def locate(c):
            doc = self.docs[c.document_index]["name"]
            if c.type == "content_block_location":  # text mode: one block per page
                return doc, c.start_block_index + 1
            return doc, c.start_page_number

        return self._to_answer(response, started, locate)


class SearchAssistant(_Base):
    """Design B: keyword search picks the most relevant passages; only those go to Claude."""

    approach = "B: search first"
    WORDS, OVERLAP, TOP_K = 120, 40, 5

    def __init__(self, doc_set: str = "cafe", top_k: int | None = None):
        super().__init__(doc_set)
        if top_k:
            self.TOP_K = top_k
            self.approach = f"B: search first (top {top_k})"
        self.passages = []  # {"doc", "page", "text"}
        for doc in self.docs:
            for page_number, page_text in enumerate(doc["pages"], 1):
                words = page_text.split()
                for start in range(0, max(len(words) - self.OVERLAP, 1), self.WORDS - self.OVERLAP):
                    chunk = " ".join(words[start:start + self.WORDS])
                    if chunk:
                        self.passages.append({"doc": doc["name"], "page": page_number, "text": chunk})
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(p["text"] for p in self.passages)

    def search(self, question: str) -> list[dict]:
        scores = cosine_similarity(self.vectorizer.transform([question]), self.matrix)[0]
        return [self.passages[i] for i in scores.argsort()[::-1][:self.TOP_K]]

    def ask(self, question: str) -> Answer:
        started = time.time()
        found = self.search(question)
        blocks = [{
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": p["text"]},
            "title": f"{p['doc']}.pdf, page {p['page']}",
            "citations": {"enabled": True},
        } for p in found]
        response = self._call(blocks + [{"type": "text", "text": question}])
        locate = lambda c: (found[c.document_index]["doc"], found[c.document_index]["page"])
        answer = self._to_answer(response, started, locate)
        answer.passages = [f"{p['doc']} p.{p['page']}" for p in found]
        return answer


if __name__ == "__main__":
    import sys
    doc_set = "esg" if "--esg" in sys.argv else "cafe"
    question = " ".join(a for a in sys.argv[1:] if a != "--esg") or "What discount do staff get?"
    for assistant in (FullContextAssistant(doc_set), SearchAssistant(doc_set)):
        a = assistant.ask(question)
        print(f"\n== {a.approach} ({a.seconds:.1f}s, ${a.cost:.4f})\n{a.text}")
        for n, c in enumerate(a.citations, 1):
            print(f"  [{n}] {c.doc} p.{c.page}: \"{c.quote[:90]}\"")
