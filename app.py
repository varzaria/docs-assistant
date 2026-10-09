"""Chat page for the 'Ask our documents' assistant.

Run with:  streamlit run app.py

Ask with one design, or compare both side by side: each answer shows its time,
cost and the pages it cites.
"""

from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from assistant import DOC_SETS, FullContextAssistant, SearchAssistant, load_documents

st.set_page_config(page_title="Ask Our Documents", page_icon="📚", layout="wide")
st.markdown("<style>.block-container {padding-top: 2rem;}</style>", unsafe_allow_html=True)

DESIGNS = {"A: read everything": FullContextAssistant, "B: search first": SearchAssistant}
MODES = ["Compare both designs", "A: read everything", "B: search first"]

SETS = {
    "cafe": {
        "label": "☕ Kildare Craft Coffee staff documents",
        "title": "Ask our documents",
        "intro": "Kildare Craft Coffee: answers from the staff handbook, food safety procedures, purchasing policy, "
                 "equipment guide and the latest policy update, with the page each answer comes from.",
        "placeholder": "Ask a question about our policies and procedures",
        "examples": [
            "What discount do staff get?",
            "A Leinster Dairy delivery arrives at 9°C. Should I accept it?",
            "What breaks do I get on a 7-hour shift?",
            "What is the Wi-Fi password?",
        ],
    },
    "esg": {
        "label": "🌍 Irish sustainability reports",
        "title": "Ask the sustainability reports",
        "intro": "Answers from three public reports: Kerry Group Annual Report 2025, Ryanair FY26 Sustainability "
                 "Statement and Bank of Ireland Sustainability Report 2024 (467 pages), with page citations.",
        "placeholder": "Ask about targets, emissions, people or finance",
        "examples": [
            "Has Bank of Ireland reached 100% renewable electricity?",
            "When do Kerry Group and Ryanair each aim to reach net zero?",
            "What is Ryanair's target for sustainable aviation fuel?",
            "What is Glanbia's Scope 3 emissions target?",
        ],
    },
}

DOC_NAMES = {
    "staff_handbook": "Staff Handbook",
    "food_safety": "Food Safety Procedures",
    "purchasing_policy": "Purchasing and Supplier Policy",
    "equipment_guide": "Equipment Guide",
    "policy_update_jan_2026": "Policy Update, January 2026",
    "kerry_annual_report_2025": "Kerry Group Annual Report 2025",
    "ryanair_sustainability_statement_fy26": "Ryanair Sustainability Statement FY26",
    "bank_of_ireland_sustainability_report_2024": "Bank of Ireland Sustainability Report 2024",
}


def doc_name(stem: str) -> str:
    return DOC_NAMES.get(stem, stem.replace("_", " ").title())


@st.cache_resource
def get_assistant(design: str, doc_set: str):
    return DESIGNS[design](doc_set)


@st.cache_resource
def available_sets() -> dict:
    return {key: load_documents(DOC_SETS[key]["folder"]) for key in SETS}


def ask(question: str, designs: list[str], doc_set: str) -> list:
    """Ask each chosen design; when comparing, both run at the same time."""
    assistants = [get_assistant(d, doc_set) for d in designs]  # created here, not inside the worker threads
    with ThreadPoolExecutor(max_workers=len(assistants)) as pool:
        return list(pool.map(lambda a: a.ask(question), assistants))


def show_answer(answer) -> None:
    with st.container(border=True):
        st.markdown(f"**{answer.approach}** &nbsp; :gray[{answer.seconds:.1f} s · \\${answer.cost:.3f}]")
        st.markdown(answer.text.replace("$", "\\$"))
        if answer.citations:
            with st.expander(f"Sources ({len(answer.citations)})"):
                for n, c in enumerate(answer.citations, 1):
                    st.markdown(f"**[{n}] {doc_name(c.doc)}, page {c.page}**")
                    st.caption(f"“{' '.join(c.quote.split())}”".replace("$", "\\$"))


def show_answers(answers: list) -> None:
    for col, answer in zip(st.columns(len(answers)), answers):
        with col:
            show_answer(answer)


# --- Sidebar -----------------------------------------------------------------------

docs_by_set = available_sets()
usable = [k for k in SETS if docs_by_set[k]]

with st.sidebar:
    st.header("📚 Ask Our Documents")
    st.caption("Answers with page citations · two designs compared")
    doc_set = st.radio("Documents", usable, format_func=lambda k: SETS[k]["label"])
    mode = st.radio("Design", MODES, help="A sends every document with each question. B searches for the most "
                    "relevant passages and sends only those. Compare runs both on the same question.")
    if doc_set == "esg" and mode != "B: search first":
        st.warning("Design A sends all 467 pages: about \\$2.45 for the first question, then about \\$0.10 "
                   "per question while the reports stay cached (5 minutes).")
    if "esg" not in usable:
        st.caption("Run `py download_esg_reports.py` to add the sustainability reports.")
    st.divider()
    st.caption("**Documents**")
    for doc in docs_by_set[doc_set]:
        n = len(doc["pages"])
        st.caption(f"📄 {doc_name(doc['name'])} ({n} page{'s' if n != 1 else ''})")
    st.divider()
    if st.button("Clear conversation", width="stretch"):
        st.session_state.messages = []

# Each document set keeps its own conversation.
if st.session_state.get("active_set") != doc_set:
    st.session_state.active_set = doc_set
    st.session_state.messages = []

info = SETS[doc_set]
st.subheader(info["title"])
st.caption(info["intro"])

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            show_answers(message["content"])

if not st.session_state.messages and "pending" not in st.session_state:
    st.caption("Try one of these:")
    for col, example in zip(st.columns(len(info["examples"])), info["examples"]):
        if col.button(example, width="stretch"):
            st.session_state.pending = example
            st.rerun()

question = st.chat_input(info["placeholder"]) or st.session_state.pop("pending", None)
if question:
    designs = list(DESIGNS) if mode == "Compare both designs" else [mode]
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Checking the documents..."):
            answers = ask(question, designs, doc_set)
        show_answers(answers)
    st.session_state.messages.append({"role": "assistant", "content": answers})
