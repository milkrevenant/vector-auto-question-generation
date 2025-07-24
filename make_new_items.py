# make_new_items.py  ◆◆◆ 2025‑07‑24 수정 ◆◆◆
from pathlib import Path
import os, re, json, textwrap, datetime
import chromadb
from openai import OpenAI

# ───────────────────────── ❶ 설정값 ─────────────────────────
DB_PATH      = Path(os.getenv("SN_DB_PATH", "./sn_csat.db"))
EMBED_MODEL  = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
CHAT_MODEL   = os.getenv("OPENAI_CHAT_MODEL",  "gpt-4.1-mini")
N_QUESTIONS  = int(os.getenv("SN_NUM_Q",  "3"))
MAX_EXAMPLES = int(os.getenv("SN_MAX_EX", "2"))
TEMP         = float(os.getenv("SN_TEMP",  "0.7"))

openai = OpenAI()
col = chromadb.PersistentClient(path=str(DB_PATH)).get_collection("sn_csat_openai")

# ───────────────────────── ❷ 함수 ──────────────────────────
def embed(text: str):
    return openai.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding

def build_prompt(passage: str, examples: list[dict]) -> list[dict]:
    ex_blocks = []
    for ex in examples[:MAX_EXAMPLES]:
        meta, doc = ex["meta"], ex["doc"]
        q_type  = meta.get("q_type")  or meta.get("type") or "유형 미상"
        opt_fmt = meta.get("opt_type") or "5지선다"
        ex_blocks.append(f"[예시 문제] 유형={q_type} / 선택지={opt_fmt}\n{doc}")

    sys = textwrap.dedent(f"""
        너는 **한국 수능 국어 출제위원**이다.
        ‣ 아래 ‘새 지문’을 그대로 활용해 **{N_QUESTIONS}개 5지선다** 문제를 만든다.
        ‣ 최소 **1 문제 이상**은 (보기) 자료를 제시해야 한다.
        ‣ 난이도는 수능 국어 ‘상’(상위 20 %) 수준.
        ‣ 각 문항마다 혼동 가능한 고품질 오답, **정답**, 간단 **해설**을 포함.
        ‣ 출력은 다음 JSON 스키마를 따른다. 불필요한 필드는 넣지 말 것.
          [
            {{
              "문제": "...",
              "보기": "㉠ ... / ㉡ ...",      # (보기) 없는 문항은 생략
              "선택지": ["① ...", "② ...", "③ ...", "④ ...", "⑤ ..."],
              "정답": "③",
              "해설": "..."
            }}, …
          ]
        반드시 **유효한 JSON만** 반환한다.
    """).strip()

    user = "# 새 지문\n" + passage.strip() + "\n\n" + "\n\n".join(ex_blocks)

    return [
        {"role": "system", "content": sys},
        {"role": "user",   "content": user}
    ]

def generate_items(passage: str, examples: list[dict]) -> str:
    msgs = build_prompt(passage, examples)
    resp = openai.chat.completions.create(
        model=CHAT_MODEL,
        temperature=TEMP,
        messages=msgs,
    )
    return resp.choices[0].message.content.strip()

# ───────────────────────── ❸ 메인 ─────────────────────────
if __name__ == "__main__":
    passage = input("🔍 새 지문 전문을 붙여 넣으세요:\n")

    # 예시: 상위 50 개에서 MAX_EXAMPLES만 사용 (그룹 필터 제거)
    vec   = embed(passage)
    hits  = col.query(query_embeddings=[vec],
                      n_results=50,
                      include=["documents", "metadatas"])
    examples = [
        {"meta": m, "doc": d}
        for d, m in zip(hits["documents"][0], hits["metadatas"][0])
    ][:MAX_EXAMPLES]

    print(f"\n📑 예시 세트 {len(examples)}개 확보 (MAX_EXAMPLES={MAX_EXAMPLES})")

    print("🛠️  LLM에 새 문제 생성 요청…")
    output = generate_items(passage, examples)

    print("\n🆕 생성 결과 ↓↓↓\n" + "="*60)
    print(output)
    print("="*60)

    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    Path(f"generated_items_{ts}.json").write_text(output, encoding="utf-8")