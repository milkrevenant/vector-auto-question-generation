# ▶ pip install openai chromadb
import chromadb, re, os, json
from openai import OpenAI

DB = "./sn_csat.db"; COL = "sn_csat_openai"
EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-large")
TOP_K = 20                  # HNSW 1차 후보
GROUP_PICK = 2              # 지문 2개 선택

# --- optional content‑type filter ------------------------------------------------
desired_type = input("📂 원하는 글 종류를 입력하세요 (예: 시, 고전소설, 수필, 독서 등). "
                     "비우면 모든 유형 허용: ").strip()
print(f"   → 유형 필터: {'없음(전체)' if not desired_type else desired_type}")

cli = OpenAI()
col = chromadb.PersistentClient(path=DB).get_collection(COL)

def embed(text):
    return cli.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding

def extract_group(doc_id: str):
    # 예: 23_11_37_2  →  23_11_37
    m = re.match(r"(\d{2}_\d{2}_\d{2})_", doc_id)
    return m.group(1) if m else doc_id

query = input("🔍 새 지문 전문을 붙여 넣으세요:\n") 
q_vec = embed(query)

hits = col.query(query_embeddings=[q_vec], n_results=TOP_K)
ids    = hits["ids"][0]
metas  = hits["metadatas"][0]

# 1) 그룹 키를 모으고 상위 2개 선정
uniq_groups = []
for _id, meta in zip(ids, metas):
    # 유형 필터: type 메타데이터에 원하는 문자열이 포함되어야 함
    if desired_type and desired_type not in str(meta.get("type", "")):
        continue

    g = extract_group(_id)
    if g not in uniq_groups:
        uniq_groups.append(g)

    if len(uniq_groups) == GROUP_PICK:
        break

print("\n선택된 지문 그룹:", uniq_groups)

# 2) 각 그룹에 속한 모든 문제 세트 가져오기
all_sets = []
for g in uniq_groups:
    where_filter = {"group": g}
    if desired_type:
        where_filter["type"] = desired_type
    group_docs = col.get(where=where_filter)
    for doc, meta in zip(group_docs["documents"], group_docs["metadatas"]):
        all_sets.append({"meta": meta, "doc": doc})

# 3) 보기 좋게 출력
for i, s in enumerate(all_sets, 1):
    print(f"\n=== 세트 {i} / 그룹 {extract_group(s['meta']['id'])} ===")
    print(s["doc"][:800], "..." if len(s["doc"]) > 800 else "")