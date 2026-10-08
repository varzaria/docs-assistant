"""Chat page for the 'Ask our documents' assistant.

Run with:  streamlit run app.py
"""

import streamlit as st

from assistant import DOC_SETS, FullContextAssistant, SearchAssistant, load_documents

st.set_page_config(page_title="Ask our documents", page_icon="☕", layout="centered")

DESIGNS = {
    "A: read everything": FullContextAssistant,
    "B: search first": SearchAssistant,
}
SETS = {
    "cafe": {
        "label": "☕ Kildare Craft Coffee staff documents",
        "title": "☕ Ask our documents",
        "intro": "Kildare Craft Coffee: answers from the staff handbook, food safety procedures, purchasing policy, "
                 "equipment guide and the latest policy updates, with the page each answer comes from.",
        "placeholder": "Ask a question about our policies and procedures",
        "examples": [
            "What discount do staff get?",
            "The fridge is showing 7°C. What should I do?",
            "Is our oat milk gluten free?",
            "The espresso machine is leaking on a Saturday. What should I do?",
            "What is the Wi-Fi password?",
        ],
    },
    "esg": {
        "label": "🌍 Irish sustainability reports",
        "title": "🌍 Ask the sustainability reports",
        "intro": "Answers from three public reports: Kerry Group Annual Report 2025, Ryanair FY26 Sustainability "
                 "Statement and Bank of Ireland Sustainability Report 2024 (467 pages), with page citations.",
        "placeholder": "Ask about targets, emissions, people or finance",
        "examples": [
            "When do Kerry Group and Ryanair each aim to reach net zero?",
            "What is Ryanair's target for sustainable aviation fuel?",
            "Has Bank of Ireland reached 100% renewable electricity?",
            "What is Glanbia's Scope 3 emissions target?",
        ],
    },
}


@st.cache_resource
def get_assistant(design: str, doc_set: str):
    return DESIGNS[design](doc_set)


@st.cache_resource
def available_sets() -> dict:
    return {key: load_documents(DOC_SETS[key]["folder"]) for key in SETS}


docs_by_set = available_sets()

with st.sidebar:
    st.header("Settings")
    usable = [k for k in SETS if docs_by_set[k]]
    doc_set = st.radio("Documents", usable, format_func=lambda k: SETS[k]["label"])
    design = st.radio("Design", list(DESIGNS), help="A sends every document with each question. "
                      "B searches for the most relevant passages and sends only those.")
    if doc_set == "esg" and design.startswith("A"):
        st.warning("Design A sends all 467 pages: about \\$2.45 for the first question, then about \\$0.10 "
                   "per question while the reports stay cached (5 minutes).")
    if "esg" not in usable:
        st.caption("Run `py download_esg_reports.py` to add the sustainability reports.")
    st.divider()
    st.subheader("Documents")
    for doc in docs_by_set[doc_set]:
        n = len(doc["pages"])
        st.caption(f"📄 {doc['name'].replace('_', ' ')} ({n} page{'s' if n != 1 else ''})")
    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []

# Each document set keeps its own conversation.
if st.session_state.get("active_set") != doc_set:
    st.session_state.active_set = doc_set
    st.session_state.messages = []

info = SETS[doc_set]
st.title(info["title"])
st.caption(info["intro"])


def show_answer(answer) -> None:
    st.markdown(answer.text.replace("$", "\\$"))
    if answer.citations:
        with st.expander(f"Sources ({len(answer.citations)})"):
            for n, c in enumerate(answer.citations, 1):
                st.markdown(f"**[{n}] {c.doc.replace('_', ' ')}, page {c.page}**")
                st.caption(f"“{' '.join(c.quote.split())}”")
    st.caption(f"{answer.approach} · {answer.seconds:.1f} s · \\${answer.cost:.3f}")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            show_answer(message["content"])

if not st.session_state.messages:
    st.write("Try one of these:")
    for example in info["examples"]:
        if st.button(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun()

question = st.chat_input(info["placeholder"]) or st.session_state.pop("pending", None)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Checking the documents..."):
            answer = get_assistant(design, doc_set).ask(question)
        show_answer(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
