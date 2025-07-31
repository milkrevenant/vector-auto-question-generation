import os, glob, json, chromadb, tiktoken
import hashlib, re
import numpy as np
from scipy.spatial.distance import cosine
from kiwipiepy import Kiwi
import time
from openai import RateLimitError, APIError, APIConnectionError, Timeout
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
 # ── 유사도 계산용 ────────────────────────────
kiwi = Kiwi()                 # Pure‑Python 형태소 분석기 (Java 불필요)

def pos_set(text: str):
    "텍스트를 형태소 품사 시퀀스로 변환해 집합으로 반환"
    return {tok.tag for tok in kiwi.tokenize(text)}

def pos_jaccard(a_set: set, b_set: set) -> float:
    "품사 집합 Jaccard 유사도 (0~1)"
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)

def cosine_sim(v1: list, v2: list) -> float:
    "코사인 유사도 (−1~1) → 0~1 정규화"
    return 1 - cosine(v1, v2)   # scipy 반환은 distance
from openai import OpenAI

# ── ❶ 경로 설정 ──────────────────────────────
SRC_DIR = "/Users/stillclie_mac/Documents/ug/snoriginal/db"
DB_PATH = "./sn_csat.db"               # DuckDB 파일
COL_NAME = "sn_csat_openai"

# ── ❷ 모델 & 도구 초기화 ─────────────────────
# 사용할 임베딩 모델 (환경변수로 덮어쓰기 가능)
EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-large")
print(f"🔧  Using embedding model: {EMBED_MODEL}")

openai  = OpenAI(timeout=60)   # 60‑sec client‑side timeout
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

pos_sets = []      # passage별 품사 집합 보관
ids, docs, metas = [], [], []
for path in files:
    with open(path, encoding="utf-8") as f:
        item = json.load(f)
    # 질문(question)이 없으면 스킵
    if not item.get("question"):
        print(f"⚠️  Skip {path} (missing question)")
        continue

    ids.append(item["id"])
    docs.append(merge_text(item))
    # 품사 집합 저장 (지문/context만 사용)
    passage_text = item.get("passage") or item.get("context_box") or ""
    pos_sets.append(pos_set(passage_text))
    # 메타데이터에서 None, dict, list 타입 값을 제거(Chroma는 dict/list 허용하지 않음)
    clean_meta = {}
    for k, v in item.items():
        if k in ("passage", "question", "options"):
            continue
        if v is None:
            continue
        # primitive 타입만 허용
        if isinstance(v, (str, int, float, bool)):
            clean_meta[k] = v
    # ― 그룹 해시 추가 ―
    clean_meta["group"] = passage_hash(item)
    # 원본 JSON 파일 경로 저장
    clean_meta["file_path"] = path
    metas.append(clean_meta)

def embed(batch, max_retry=5, backoff=2):
    """
    Call OpenAI embedding with exponential back‑off.
    Returns list[vector]. Raises last error after retries.
    """
    for attempt in range(1, max_retry + 1):
        try:
            res = openai.embeddings.create(model=EMBED_MODEL, input=batch)
            return [d.embedding for d in res.data]
        except (RateLimitError, APIError, APIConnectionError, Timeout) as e:
            wait = backoff ** attempt
            print(f"⚠️  Embed attempt {attempt}/{max_retry} failed: {e} → retry in {wait}s")
            time.sleep(wait)
        except Exception as e:
            print(f"❌  Unexpected embed error: {e}")
            raise
    raise RuntimeError(f"Embedding failed after {max_retry} attempts")

 # ── ❹ OpenAI 임베딩 (64개씩 배치) ───────────── 갯수 상관없음
BATCH = 64
embs = []
for i in range(0, len(docs), BATCH):
    embs.extend(embed(docs[i:i+BATCH]))
    print(f"  → Embedded {len(embs)}/{len(docs)}")

# ── ❹‑b 의미·형식 최대 유사도 계산 ───────────
max_sem_sims   = []
max_struct_sims = []

for i, emb_i in enumerate(embs):
    if i == 0:                    # 첫 항목은 자기 자신뿐
        max_sem_sims.append(1.0)
        max_struct_sims.append(1.0)
        continue

    sem_scores   = [cosine_sim(emb_i, embs[j]) for j in range(i)]
    struct_scores = [pos_jaccard(pos_sets[i], pos_sets[j]) for j in range(i)]

    max_sem_sims.append(max(sem_scores))
    max_struct_sims.append(max(struct_scores))

# 메타데이터에 유사도 기록
for i, meta in enumerate(metas):
    meta["max_sem_sim"]   = round(max_sem_sims[i], 4)
    meta["max_struct_sim"] = round(max_struct_sims[i], 4)

# ── ❺ Chroma 컬렉션에 저장 ───────────────────
col.add(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
print(f"✅  {len(ids)} items stored in {DB_PATH}:{COL_NAME}")