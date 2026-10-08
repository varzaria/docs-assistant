# Case study: an AI assistant for company documents, and how to choose its design

**Clients:** a small café (fictional, Kildare Craft Coffee Ltd) and, as a stress test, three public Irish sustainability reports
**Tools:** Python, Claude (citations and prompt caching), keyword search, Streamlit
**Outcome:** 100% correct answers with page citations on both document sets, plus evidence for which design to use at which size and cost

## 1. The problem

Staff keep asking managers questions the documents already answer: "How much leave do I get?", "Is the oat milk gluten-free?", "Who do I call when the machine leaks?". Analysts face the same problem at a larger scale with long annual and sustainability reports. An AI assistant only helps if people can trust it, so it must cite its sources, give the current rule when policies change, and admit when it doesn't know.

## 2. The decision every client faces

There are two common ways to build this:

- **A: read everything.** Give the AI all the documents with each question. Simple, nothing to maintain, but the cost grows with the size of the documents.
- **B: search first.** Find the most relevant passages and give the AI only those. Cheaper per question, but only as good as the search.

Rather than guess, I built both and measured them.

## 3. How it was tested

- **Café documents:** 5 documents, 10 pages, with deliberate traps: a memo that changes handbook rules, answers spread across two documents, details in tables, and questions the documents can't answer. 35 questions.
- **Sustainability reports:** Kerry Group (290 pages), Ryanair (119) and Bank of Ireland (58): 467 pages of real reports. 19 questions, including comparisons across companies and questions the reports can't answer.
- Every answer was graded against a reference answer by a separate AI call, and every citation was checked against the pages that contain the answer.

## 4. Results

| | Café: A | Café: B | Reports: A | Reports: B (5 passages) | Reports: B (20 passages) |
| --- | --- | --- | --- | --- | --- |
| Correct | **35 / 35** | 33 / 35 | **19 / 19** | 9 / 19 | 17 / 19 |
| Cost per question | $0.010 | $0.017 | $0.23 | $0.019 | $0.044 |
| Time per question | 5.0 s | 4.4 s | 7.9 s | 4.5 s | 4.3 s |

- **Small documents: read everything.** It was both the most accurate and the cheapest, because cached documents cost almost nothing to resend.
- **Large documents: it depends on volume.** Reading everything stayed perfect but costs about 10–25 cents per question. Search with 5 passages missed half the answers; with 20 passages it got 17 / 19 at about a fifth of the cost.
- **How the assistant failed matters.** Almost every miss was "I couldn't find it", not an invented figure. That is the safer failure, but the interface should make clear that "not found" can mean "not retrieved".

## 5. Risks and how they are handled

| Risk | Mitigation |
| --- | --- |
| The AI invents an answer | It is instructed to answer only from the documents and to say when it can't find something; every statement is cited with a page, and unanswerable questions are part of the test set. |
| Outdated rules | Tested directly: the assistant gave the January 2026 memo's rules (for example a 25% discount, not the handbook's 20%) and said what changed. |
| "Not found" when the answer exists (search design) | Retrieve more passages, test better search before go-live, and show users which pages were searched. |
| Costs grow with document size | Measured before go-live; caching cuts repeat costs by about 95%; choose the design per document set. |
| Confidential documents sent to an AI provider | Check the provider's data-retention terms and the client's GDPR obligations before go-live. |

## 6. Recommendation for a real deployment

1. Start with **read everything** for handbooks and policies: it is the most accurate, cheapest at this size, and has no search to maintain.
2. For large document sets, estimate question volume first: at a few hundred questions a month, reading everything costs tens of euro and is the safest choice; at thousands, invest in better search and test it the same way.
3. Collect real staff questions for a month and use them as the test set before and after any change.
