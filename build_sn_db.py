import os, glob, json, chromadb, tiktoken
import hashlib, re
 # ── 그룹 해시 생성 ─────────────────────────
def canonical_passage(item: dict) -> str:
    """passage 또는 context_box를 공백 1칸으로 정규화해 반환"""
    txt = (item.get("passage") or item.get("context_box") or "")
    return " ".join(txt.split())

def passage_hash(item: dict, length: int = 12) -> str:
    """
    동일 지문이면 파일명이 달라도 동일 해시를 얻도록 SHA‑1 기반 그룹키 생성.
    기본 12자(48bit) → 충돌 확률 1/2^48 ≈ 1.4e‑14
    """
    text = canonical_passage(item)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]
from openai import OpenAI

# ── ❶ 경로 설정 ──────────────────────────────
SRC_DIR = "/Users/stillclie_mac/Documents/ug/snoriginal/db"
DB_PATH = "./sn_csat.db"               # DuckDB 파일
COL_NAME = "sn_csat_openai"

# ── ❷ 모델 & 도구 초기화 ─────────────────────
# 사용할 임베딩 모델 (환경변수로 덮어쓰기 가능)
EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-large")
print(f"🔧  Using embedding model: {EMBED_MODEL}")

openai  = OpenAI()
client  = chromadb.PersistentClient(path=DB_PATH)
col     = client.get_or_create_collection(
             COL_NAME, metadata={"hnsw:space":"cosine"}
         )

def merge_text(item: dict) -> str:
    """
    지문 + 문제 + 선택지를 한 문자열로
    None 이나 누락 필드는 빈 문자열로 처리해 오류를 방지한다.
    """
    passage  = item.get("passage") or item.get("context_box") or ""
    question = item.get("question") or ""
    choices  = " ".join(opt.get("text", "") for opt in item.get("options", []))
    return f"{passage}\n{question}\n{choices}"

# ── ❸ 모든 JSON 파일 수집 ────────────────────
files = sorted(glob.glob(os.path.join(SRC_DIR, "*.json")))
print(f"🔍  Found {len(files)} JSON files.")

ids, docs, metas = [], [], []
for path in files:
    with open(path, encoding="utf-8") as f:
        item = json.load(f)
    # passage가 없으면 context_box로 대체할 수 있는지 확인
    if not (item.get("passage") or item.get("context_box")) or not item.get("question"):
        print(f"⚠️  Skip {path} (missing passage/context_box 또는 question)")
        continue

    ids.append(item["id"])
    docs.append(merge_text(item))
    # 메타데이터에서 None 값을 제거(Chroma는 None을 허용하지 않음)
    clean_meta = {
        k: v for k, v in item.items()
        if k not in ("passage", "question", "options") and v is not None
    }
    # ― 그룹 해시 추가 ―
    clean_meta["group"] = passage_hash(item)
    metas.append(clean_meta)

# ── ❹ OpenAI 임베딩 (128개씩 배치) ───────────── 갯수 상관없음
def embed(batch):
    res = openai.embeddings.create(
        model=EMBED_MODEL,
        input=batch
    )
    return [d.embedding for d in res.data]

BATCH = 128
embs = []
for i in range(0, len(docs), BATCH):
    embs.extend(embed(docs[i:i+BATCH]))
    print(f"  → Embedded {len(embs)}/{len(docs)}")

# ── ❺ Chroma 컬렉션에 저장 ───────────────────
col.add(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
print(f"✅  {len(ids)} items stored in {DB_PATH}:{COL_NAME}")