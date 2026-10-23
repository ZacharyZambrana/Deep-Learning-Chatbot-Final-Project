# Grassroots Furniture: Customer Service Assistant Chat Application
# Run with Streamlit:
#     streamlit run ism6564-week07-app.py
from __future__ import annotations

import time
_W7_T0 = time.perf_counter()

import hashlib, io, json, math, re, sqlite3, tempfile, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np, pandas as pd, torch
from openai import OpenAI
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

try:
    import streamlit as st
    from streamlit import runtime as _w7_runtime
    _W7_PAGE = bool(_w7_runtime.exists())
except Exception:
    _W7_PAGE = False
if _W7_PAGE:
    st.set_page_config(page_title="Grassroots Furniture Help", page_icon=":couch_and_lamp:", layout="centered")
    _w7_once = st.cache_resource(show_spinner="Loading the search models and building the index ...")
else:
    def _w7_once(fn):
        return fn

FORCE_CPU = False              # as set in the notebook
device = torch.device("cpu" if FORCE_CPU else "cuda" if torch.cuda.is_available()
                      else "mps" if torch.backends.mps.is_available() else "cpu")
MODEL, OLLAMA_URL, SEED = 'llama3.2:3b', 'http://localhost:11434/v1/', 6564
LOCAL = [Path('data'), Path('.') ]
DECLINE_MESSAGE = "I don't have that information in the Grassroots Furniture help centre. Please contact our concierge support team, who can look into it for you."
CUSTOMER_ID, TODAY = 'C-2041', '2026-10-07'
CODE = re.compile('\\b[A-Z][A-Z0-9]*-[A-Z0-9]+(?:-[A-Z0-9]+)*\\b')
NUMBER = re.compile('\\$?\\d+(?:\\.\\d+)?%?')
client = OpenAI(base_url=OLLAMA_URL, api_key='ollama')


@_w7_once
def _w7_models(device_name: str):
    return (SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=device_name),
            CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device=device_name))


EMBEDDER, RERANKER = _w7_models(str(device))


# ---- provided by the notebook
def fetch(name: str) -> str:
    """A data file as text: reads from the local data folder."""
    for d in LOCAL:
        if (d / name).exists():
            return (d / name).read_text(encoding="utf-8")
    raise FileNotFoundError(f"Cannot find {name} in {LOCAL}")


def fetch_file(name: str) -> Path:
    """A data file on disk (the database)."""
    for d in LOCAL:
        if (d / name).exists():
            return (d / name).resolve()
    raise FileNotFoundError(f"Cannot find file {name} in {LOCAL}")


def split_sentences(text: str) -> list[str]:
    """Sentences, headings and list items, in order. Joined back together they are the original text."""
    ends = [m.end() for m in re.finditer(r"(?<=[.!?])(?<!\n\d\.)\s+|\n\s*\n|\n(?=- )", text)] + [len(text)]
    units, start = [], 0
    for end in sorted(set(ends)):
        if text[start:end].strip():
            units.append(text[start:end])
            start = end
    return units


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


def _ids(allowed=None):
    return [i for i, p in enumerate(PASSAGES) if allowed is None or allowed(p)]


def meaning_search(question: str, k: int, allowed=None) -> list[int]:
    ids = _ids(allowed)
    s = E[ids] @ EMBEDDER.encode([question], normalize_embeddings=True, convert_to_numpy=True)[0]
    return [ids[i] for i in np.argsort(-s)[:k]]


def keyword_search(question: str, k: int, allowed=None) -> list[int]:
    ids = _ids(allowed)
    s = BM25.get_scores(words(question))[ids]
    return [ids[i] for i in np.argsort(-s)[:k]]


def rerank(question: str, shortlist: list[int], k: int) -> list[int]:
    """The cross-encoder reads the question with each passage; the best k, best first."""
    s = RERANKER.predict([(question, PASSAGES[i]["text"]) for i in shortlist])
    return [shortlist[i] for i in np.argsort(-s)[:k]]


def best_match(question: str, idx: list[int]) -> float:
    """The cross-encoder's score for the best of these passages (higher = a better match)."""
    idx = list(idx)
    return float(max(RERANKER.predict([(question, PASSAGES[i]["text"]) for i in idx]))) if idx else -100.0


def ask_first(question: str, idx: list[int], model_name: str = None) -> bool:
    """Ask-first guardrail: True if the model says the passages do NOT state the answer."""
    sources = "\n\n".join(f"[{PASSAGES[i]['doc_id']}]\n{PASSAGES[i]['text']}" for i in idx)
    reply, _, _ = ask_messages([{"role": "system", "content": "You check whether sources answer a question. Reply with exactly one word: YES or NO."},
                                {"role": "user", "content": f"SOURCES:\n{sources}\n\nQUESTION: {question}\n\n"
                                                            "Do the sources state the answer to this question? Reply YES or NO."}], max_tokens=3, model_name=model_name)
    return not reply.strip().upper().startswith("YES")


def normalise(text: str) -> str:
    """Money and percentages written one way, so '99 dollars' and '$99' compare equal."""
    t = text.lower().replace("–", "-")
    t = re.sub(r"(\d+) dollars? (?:and )?(\d+) cents?", r"$\1.\2", t)
    t = re.sub(r"(?<![\d.])(\d+) dollars?", r"$\1", t)
    t = re.sub(r"(\d+) ?(?:percent|per cent)", r"\1%", t)
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    t = re.sub(r"\$(\d+)\.00\b", r"$\1", t)
    return re.sub(r"\s+", " ", t)


def unsupported(answer: str, page: str) -> list[str]:
    """The hallucination check: numbers and codes in the answer that appear nowhere on the page."""
    text = re.sub(r"(?m)^\s*\d+[.)]\s", " ", answer)
    claims = CODE.findall(text) + NUMBER.findall(normalise(CODE.sub(" ", text)))
    numbers_on_page = normalise(CODE.sub(" ", page))
    bad = []
    for c in claims:
        if CODE.fullmatch(c):
            if not re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", page, re.I):
                bad.append(c)
        elif not re.search(rf"(?<![\w.]){re.escape(c)}(?!\d|\.\d)", numbers_on_page):
            bad.append(c)
    return bad


def ask_messages(messages: list[dict], max_tokens: int = 150, model_name: str = None):
    """One call to the model in Ollama: (answer, prompt tokens, seconds)."""
    t0 = time.perf_counter()
    use_model = model_name or MODEL
    r = client.chat.completions.create(model=use_model, messages=messages, temperature=0, seed=SEED, max_tokens=max_tokens)
    return (r.choices[0].message.content or "").strip(), (r.usage.prompt_tokens if r.usage else 0), time.perf_counter() - t0


def answer(message: str, history=None, facts=None, design=None, customer_id=None) -> dict:
    d = design or DESIGN
    facts, history = dict(facts or {}), list(history or [])
    order_id = facts.get("order number") if d.get("lookup") else None       # Task 4: the order this conversation has named
    row = d["lookup"](order_id, customer_id or CUSTOMER_ID) if order_id else None
    if d.get("handoff") and d["handoff"](message, facts, row):
        return dict(text=handoff_message(facts), status="handed off", sources=[], idx=[], user="", tokens=0, sec=0.0, order=None)
    idx = [int(i) for i in d["search"](message, d["k"], d["allowed"])]      # a plain list, whatever the search returns
    passages = [(PASSAGES[i]["doc_id"], PASSAGES[i]["text"]) for i in idx]
    base = dict(sources=[p[0] for p in passages], idx=idx, order=row["order_id"] if row else None)
    if row is None and d.get("decline") and d["decline"](message, idx):     # the decline rule judges passages, not a row
        return dict(text=DECLINE_MESSAGE, status="declined", user="", tokens=0, sec=0.0, **base)
    if row is not None:
        facts = {**facts, **d["order_facts"](row)}                           # the row, as facts the model can read
    user = d["augment"](message, passages, facts if d.get("memory") else None)
    msgs = [{"role": "system", "content": d["system"]}] + history[-4:] + [{"role": "user", "content": user}]
    text, n_in, sec = ask_messages(msgs)
    not_on_page = unsupported(text, user) if d.get("check") else []
    if not_on_page:                      # the customer gets the decline message; what the model wrote is kept to read
        return dict(text=DECLINE_MESSAGE, status="checked", user=user, tokens=n_in, sec=sec, model_said=text,
                    not_on_page=not_on_page, **base)
    return dict(text=text, status="answered", user=user, tokens=n_in, sec=sec, **base)


def handoff_message(facts: dict) -> str:
    order = facts.get("order number")
    return ("I can't find " + (f"order {order}" if order else "that order") + " on this account, so I'm passing your question"
            " to a member of our support team, who will reply by email.")


# ---- the team's imports, constants and functions
ORDER_SQL = '\n    SELECT o.order_id, o.status, o.placed_on, o.delivered_on, o.tracking_no, o.total,\n           i.product, i.quantity, i.unit_price, i.final_sale\n    FROM orders AS o JOIN order_items AS i USING (order_id)\n    WHERE o.order_id = ? AND o.customer_id = ?\n    ORDER BY i.line_no\n'
ORDER_NUMBER = re.compile('\\bGF-\\d+\\b', 34)


def chunk(doc: dict) -> list[dict]:
    title_line = f"# {doc['title']}"
    head, *sections = [p.strip() for p in re.split(r"(?m)^(?=## )", doc["text"])]   # head = title and any intro; then one piece per "##" section
    if sections:
        sections[0] = f"{head}\n\n{sections[0]}"                                     # the intro joins the first section
        sections[1:] = [f"{title_line}\n\n{s}" for s in sections[1:]]                # every other section carries the title so it stands on its own
    else:
        sections = [head]                                                            # an article with no "##" sections is one passage
    return [{"doc_id": doc["doc_id"], "text": text, "audience": doc["audience"], "status": doc["status"]}
            for text in sections if text.replace(title_line, "").strip("# \n\t")]    # never a passage that is only a title


def remember(facts: dict, message: str) -> dict:
    facts = dict(facts)                                   # a copy: the caller's facts are not changed
    named = ORDER_NUMBER.findall(message)
    if named:
        facts["order number"] = named[-1].upper()         # a later number replaces an earlier one
    return facts


def search_without_order_number(question: str, k: int, allowed=None) -> list[int]:
    cleaned = ORDER_NUMBER.sub("", question).strip()
    return search(cleaned, k, allowed)


def allowed(passage: dict) -> bool:
    return passage["audience"] == "public" and passage["status"] == "current"    # no internal pages, no superseded policy


def augmented(question: str, passages: list[tuple[str, str]], facts: dict | None = None) -> str:
    parts = []
    if facts:                                                                              # Task 4: what the conversation knows
        parts.append("KNOWN FACTS:\n" + "\n".join(f"- {name}: {value}" for name, value in facts.items()))
    parts.append("SOURCES:\n" + "\n\n".join(f"[{doc_id}]\n{text}" for doc_id, text in passages))
    parts.append(f"QUESTION: {question}")
    return "\n\n".join(parts)


def should_decline(question: str, idx: list[int]) -> bool:
    return ask_first(question, idx)     # the model is asked first whether the passages state the answer; NO means decline


def lookup_order(order_id: str, customer_id: str):
    rows = DB.execute(ORDER_SQL, (order_id, customer_id)).fetchall()      # parameterised query prevents SQL injection
    if not rows:                                                          # not this customer's order, or no such order
        return None
    first = rows[0]
    return {"order_id": first["order_id"], "status": first["status"], "placed_on": first["placed_on"],
            "delivered_on": first["delivered_on"], "tracking_no": first["tracking_no"], "total": first["total"],
            "items": [{"product": r["product"], "quantity": r["quantity"], "unit_price": r["unit_price"],
                       "final_sale": bool(r["final_sale"])} for r in rows]}


def order_facts(row: dict) -> dict:
    facts = {"order number": row["order_id"], "order status": row["status"], "placed on": row["placed_on"]}
    if row["delivered_on"]:
        facts["delivered on"] = row["delivered_on"]
    if row["tracking_no"]:
        facts["tracking number"] = row["tracking_no"]
    facts["items"] = "; ".join(f"{i['quantity']} x {i['product']} at ${i['unit_price']:.2f}" + (" (final sale)" if i["final_sale"] else "")
                               for i in row["items"])
    facts["order total"] = f"${row['total']:.2f}"
    return facts


def needs_person(message: str, facts: dict, row) -> bool:
    return row is None and bool(ORDER_NUMBER.search(message))   # message names an order the look-up did not find


def search(question: str, k: int, allowed=None) -> list[int]:
    shortlist = 20                                                       # how many passages each search contributes
    by_meaning = meaning_search(question, shortlist, allowed)            # passage indexes, best meaning match first
    by_words = keyword_search(question, shortlist, allowed)              # passage indexes, best keyword match first
    return rrf(by_meaning, by_words)[:k]                                 # fuse the two lists and keep the best k


def rrf(*rankings: list[int], c: int = 60) -> list[int]:
    scores = defaultdict(float)                          # passage index -> its fused score so far
    for ranking in rankings:                             # each search's list of passage indexes, best first
        for rank, i in enumerate(ranking, start=1):      # rank 1 for the first passage in the list
            scores[i] += 1 / (c + rank)                  # a passage earns more the nearer the top it is
    return sorted(scores, key=lambda i: -scores[i])      # best fused score first


THE_CUT = chunk                  # the cut chosen in Task 1: CUT = 'section'


# ---- the order database, the index and the final design
@_w7_once
def _w7_database(name: str) -> str:
    return str(fetch_file(name))


DB = sqlite3.connect(Path(_w7_database('grassroots.db')).as_uri() + '?mode=ro', uri=True)     # read-only
DB.row_factory = sqlite3.Row


@_w7_once
def _w7_index(app_version: str):
    docs = [json.loads(line) for line in fetch('kb_docs.jsonl').splitlines() if line.strip()]
    passages = [p for d in docs for p in THE_CUT(d)]
    vectors = EMBEDDER.encode([p['text'] for p in passages], normalize_embeddings=True, batch_size=64, convert_to_numpy=True)
    return docs, passages, vectors, BM25Okapi([words(p['text']) for p in passages])


try:
    _W7_VERSION = hashlib.sha1(Path(__file__).read_bytes()).hexdigest()
except Exception:
    _W7_VERSION = "unknown"
DOCS, PASSAGES, E, BM25 = _w7_index(_W7_VERSION)
BY_ID = {d['doc_id']: d for d in DOCS}
DESIGN = dict(search=search_without_order_number, k=5, allowed=allowed, system='You are Grassroots Furniture\'s help-centre assistant. Answer ONLY from the sources and known facts you are given, never from your own knowledge. Cite the source id in square brackets, like [KB-001], after each fact you use. If the sources do not contain the answer, say so: reply "I don\'t have that information in the Grassroots Furniture help centre." Be brief.', augment=augmented, decline=should_decline, check=True, lookup=lookup_order, order_facts=order_facts, handoff=needs_person, memory=True)

# ------------------------------------------------------------------------------------------- the page
if _W7_PAGE:
    _w7_names = {r["customer_id"]: r["name"] for r in DB.execute("SELECT customer_id, name FROM customers ORDER BY customer_id")}
    _w7_who = list(_w7_names)
    st.title("Grassroots Furniture Concierge")
    st.caption(f"Customer Service Chatbot · {MODEL} in Ollama, answering from {len(PASSAGES)} help-centre passages "
               "and from the signed-in customer's orders")
    with st.sidebar:
        customer = st.selectbox("Signed in as", _w7_who, index=_w7_who.index(CUSTOMER_ID) if CUSTOMER_ID in _w7_who else 0,
                                format_func=lambda c: f"{c} - {_w7_names[c]}")
        st.header("The design")
        _open = sum(1 for p in PASSAGES if DESIGN["allowed"] is None or DESIGN["allowed"](p))
        st.markdown(f"- the cut: **{THE_CUT.__name__}**, {len(PASSAGES)} passages\n- passages per answer: **{DESIGN['k']}**\n"
                    f"- answer check: **{'on' if DESIGN['check'] else 'off'}**\n"
                    f"- passages a customer can be answered from: **{_open} of {len(PASSAGES)}**\n"
                    f"- order look-up: **{'on, read-only' if DESIGN.get('lookup') else 'off'}**")
        fresh = st.button("New conversation")
    if fresh or st.session_state.get("customer") != customer:
        for key in ("history", "facts", "log"):
            st.session_state.pop(key, None)
    st.session_state.customer = customer
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("facts", {})
    st.session_state.setdefault("log", [])
    for turn in st.session_state.log:
        with st.chat_message(turn["role"]):
            st.markdown(turn["text"])
            if turn.get("meta"):
                st.caption(turn["meta"])
    message = st.chat_input("Ask Grassroots Furniture concierge")
    if message:
        with st.chat_message("user"):
            st.markdown(message)
        try:
            st.session_state.facts = remember(st.session_state.facts, message)
            r = answer(message, st.session_state.history, st.session_state.facts, customer_id=customer)
        except Exception as exc:
            st.error(f"The assistant could not answer: {type(exc).__name__}: {exc}")
            st.info(f"Is Ollama running, and is {MODEL} pulled (`ollama pull {MODEL}`)?")
            st.stop()
        meta = f"{r['status']} - {time.perf_counter() - _W7_T0:.1f} s for the whole turn (the model's call: {r['sec']:.2f} s)"
        if r["sources"]:
            meta += " - sources: " + ", ".join(dict.fromkeys(r["sources"]))
        if r.get("order"):
            meta += f" - order row: {r['order']}"
        if st.session_state.facts:
            meta += " - remembered: " + ", ".join(f"{k} {v}" for k, v in st.session_state.facts.items())
        with st.chat_message("assistant"):
            st.markdown(r["text"])
            st.caption(meta)
        st.session_state.history += [{"role": "user", "content": message}, {"role": "assistant", "content": r["text"]}]
        st.session_state.log += [{"role": "user", "text": message}, {"role": "assistant", "text": r["text"], "meta": meta}]
elif __name__ == "__main__":
    print("This file is a Streamlit page. Run it with:  streamlit run ism6564-week07-app.py")
