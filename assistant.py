"""'Ask our documents' assistant: answers staff questions from company PDFs, with page citations.

Two designs, so they can be compared:
  FullContextAssistant  sends every document with every question (cached after the first call)
  SearchAssistant       finds the most relevant passages with keyword search and sends only those

Both use Claude's built-in citations, so every statement links to a document and page.
"""

import base64
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).parent
DOCS_DIR = ROOT / "documents"
MODEL = "claude-opus-5-5"
EFFORT = "medium"
PRICES = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}  # USD per million tokens

SYSTEM_PROMPT = """You answer questions from staff at Kildare Craft Coffee Ltd, using only the company documents provided.

- Base every statement on the documents and cite them. Do not add outside knowledge or assumptions.
- If the documents do not answer the question, say clearly that you could not find it in the company documents and suggest asking the café manager. Do not guess.
- Some documents are updated by later ones, such as a memo. If documents disagree, give the most recent rule, say when it changed, and mention what it replaced.
- Answer in one to four short sentences or a short list, in plain English, as if replying to a colleague."""


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


def load_documents() -> list[dict]:
    docs = []
    for path in sorted(DOCS_DIR.glob("*.pdf")):
        pages = [" ".join(p.extract_text().split()) for p in PdfReader(path).pages]
        docs.append({"name": path.stem, "path": path, "pages": pages})
    return docs


class _Base:
    approach = ""

    def __init__(self):
        load_dotenv(ROOT / ".env")
        self.client = anthropic.Anthropic()
        self.docs = load_documents()

    def _call(self, content: list[dict]):
        return self.client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
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
    """Design A: every document goes to Claude with every question."""

    approach = "A: read everything"

    def __init__(self):
        super().__init__()
        self.blocks = []
        for doc in self.docs:
            self.blocks.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf",
                           "data": base64.standard_b64encode(doc["path"].read_bytes()).decode()},
                "title": f"{doc['name']}.pdf",
                "citations": {"enabled": True},
            })
        self.blocks[-1]["cache_control"] = {"type": "ephemeral"}  # cache all documents after the first question

    def ask(self, question: str) -> Answer:
        started = time.time()
        response = self._call(self.blocks + [{"type": "text", "text": question}])
        locate = lambda c: (self.docs[c.document_index]["name"], c.start_page_number)
        return self._to_answer(response, started, locate)


class SearchAssistant(_Base):
    """Design B: keyword search picks the most relevant passages; only those go to Claude."""

    approach = "B: search first"
    WORDS, OVERLAP, TOP_K = 120, 40, 5

    def __init__(self):
        super().__init__()
        self.passages = []  # {"doc", "page", "text"}
        for doc in self.docs:
            for page_number, page_text in enumerate(doc["pages"], 1):
                words = page_text.split()
                for start in range(0, max(len(words) - self.OVERLAP, 1), self.WORDS - self.OVERLAP):
                    self.passages.append({"doc": doc["name"], "page": page_number,
                                          "text": " ".join(words[start:start + self.WORDS])})
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
    question = " ".join(sys.argv[1:]) or "What discount do staff get?"
    for assistant in (FullContextAssistant(), SearchAssistant()):
        a = assistant.ask(question)
        print(f"\n== {a.approach} ({a.seconds:.1f}s, ${a.cost:.4f})\n{a.text}")
        for n, c in enumerate(a.citations, 1):
            print(f"  [{n}] {c.doc} p.{c.page}: \"{c.quote[:90]}\"")
