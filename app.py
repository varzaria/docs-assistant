"""Chat page for the 'Ask our documents' assistant.

Run with:  streamlit run app.py
"""

import streamlit as st

from assistant import ROOT, FullContextAssistant, SearchAssistant, load_documents

st.set_page_config(page_title="Ask our documents", page_icon="☕", layout="centered")

DESIGNS = {
    "A: read everything": FullContextAssistant,
    "B: search first": SearchAssistant,
}
EXAMPLES = [
    "What discount do staff get?",
    "The fridge is showing 7°C. What should I do?",
    "Is our oat milk gluten free?",
    "The espresso machine is leaking on a Saturday. What should I do?",
    "What is the Wi-Fi password?",
]


@st.cache_resource
def get_assistant(design: str):
    return DESIGNS[design]()


with st.sidebar:
    st.header("Settings")
    design = st.radio("Design", list(DESIGNS), help="A sends every document with each question. "
                      "B searches for the most relevant passages and sends only those.")
    st.divider()
    st.subheader("Documents")
    for doc in load_documents(ROOT / "documents"):
        n = len(doc["pages"])
        st.caption(f"📄 {doc['name'].replace('_', ' ')} ({n} page{'s' if n != 1 else ''})")
    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []

st.title("☕ Ask our documents")
st.caption("Kildare Craft Coffee: answers from the staff handbook, food safety procedures, purchasing policy, "
           "equipment guide and the latest policy updates, with the page each answer comes from.")

if "messages" not in st.session_state:
    st.session_state.messages = []


def show_answer(answer) -> None:
    st.markdown(answer.text)
    if answer.citations:
        with st.expander(f"Sources ({len(answer.citations)})"):
            for n, c in enumerate(answer.citations, 1):
                st.markdown(f"**[{n}] {c.doc.replace('_', ' ')}, page {c.page}**")
                st.caption(f"“{' '.join(c.quote.split())}”")
    st.caption(f"{answer.approach} · {answer.seconds:.1f} s · ${answer.cost:.3f}")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            show_answer(message["content"])

if not st.session_state.messages:
    st.write("Try one of these:")
    for example in EXAMPLES:
        if st.button(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun()

question = st.chat_input("Ask a question about our policies and procedures") or st.session_state.pop("pending", None)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Checking the documents..."):
            answer = get_assistant(design).ask(question)
        show_answer(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
