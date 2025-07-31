import os, glob, json, chromadb, tiktoken
import hashlib, re
import numpy as np
from scipy.spatial.distance import cosine
from kiwipiepy import Kiwi
import time
from sentence_transformers import SentenceTransformer

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
kiwi = Kiwi()  # Pure‑Python 형태소 분석기 (Java 불필요)

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
    return 1 - cosine(v1, v2)  # scipy 반환은 distance

# ── 읽기 난이도 지표 ───────────────────────────
def readability_kor(text: str) -> float:
    """
    간이 한국어 읽기 난이도 점수 (0=쉬움 → 1=어려움).
    - 평균 문장 길이와 평균 어절(토큰) 길이를 결합.
    - 필요에 따라 BLRD·AI-KLE 등 정식 지표로 교체 가능.
    """
    # 문장 분리
    sents = re.split(r"[\.\\?!\\n]", text.strip())
    sents = [s.strip() for s in sents if s.strip()]
    if not sents:
        return 0.0
    # 평균 문장 길이(어절 수)
    sent_lens = [len(sent.split()) for sent in sents]
    avg_sent = sum(sent_lens) / len(sent_lens)
    # 평균 어절 길이(음절 수)
    words = text.split()
    avg_word = sum(len(w) for w in words) / len(words) if words else 0
    # 가중합 (조정 가능)
    score = 0.6 * (avg_sent / 30) + 0.4 * (avg_word / 6)
    # 0~1 로 클리핑
    return round(min(max(score, 0), 1), 3)

# ── 텍스트를 최대 max_tokens 단위로 청크 ───────────────────────────
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
MAX_TOK = 256  # embed 청크 길이

def chunk_text(text: str, max_tokens: int = MAX_TOK):
    """
    주어진 문자열을 최대 max_tokens 토큰 길이로 나눠 리스트 반환.
    문장 경계를 우선 고려하되, 길이 초과 시 강제로 자름.
    """
    sents = re.split(r"(?<=[.!?\\n])", text)
    chunks, current = [], ""
    for s in sents:
        if not s.strip():
            continue
        if len(enc.encode(current + s)) <= max_tokens:
            current += s
        else:
            if current:
                chunks.append(current.strip())
            # 길면 문장 단위 무시하고 hard‑split
            while len(enc.encode(s)) > max_tokens:
                head_tokens = enc.encode(s)[:max_tokens]
                chunks.append(enc.decode(head_tokens))
                s = enc.decode(enc.encode(s)[max_tokens:])
            current = s
    if current:
        chunks.append(current.strip())
    return chunks or [text[:max_tokens]]

# ── ❶ 경로 설정 ──────────────────────────────
SRC_DIR = "/Users/stillclie_mac/Documents/ug/snoriginal/db"
DB_PATH = "./sn_csat_2.db"         # Chroma 퍼시스턴스 디렉터리(폴더명)
COL_NAME = "sn_csat_openai"        # 기존 컬렉션명 유지 (변경 원하면 이 값만 수정)

# ── ❷ 임베딩 모델 초기화 (로컬 SentenceTransformer) ─────────
# 사용할 임베딩 모델 (환경변수 EMBED_MODEL 로 덮어쓰기 가능)
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nlpai-lab/KURE-v1")
print(f"🔧  Using embedding model: {EMBED_MODEL}")

# SentenceTransformer 로컬 모델 로드
# normalize_embeddings=True 를 사용하므로 코사인/유클리드 일관성 확보
# Force CPU to avoid Apple MPS scratch‑pad OOM
_model = SentenceTransformer(EMBED_MODEL, device="cpu")
# Limit sequence length so attention buffer stays small
try:
    _model.max_seq_length = 256
except AttributeError:
    pass

# ── ❸ Chroma 컬렉션 오픈 ─────────────────────
client = chromadb.PersistentClient(path=DB_PATH)
col = client.get_or_create_collection(
    COL_NAME, metadata={"hnsw:space": "cosine"}
)

# ── 유틸: 지문+문항+선택지 합치기 ───────────────────────────

def merge_text(item: dict) -> str:
    """
    지문 + 문제 + 선택지를 한 문자열로
    None 이나 누락 필드는 빈 문자열로 처리해 오류를 방지한다.
    """
    passage = item.get("passage") or item.get("context_box") or ""
    question = item.get("question") or ""
    choices = " ".join(opt.get("text", "") for opt in item.get("options", []))
    return f"{passage}\n{question}\n{choices}"

# ── ❹ 모든 JSON 파일 수집 ────────────────────
files = sorted(glob.glob(os.path.join(SRC_DIR, "*.json")))
print(f"🔍  Found {len(files)} JSON files.")

pos_sets = []  # passage별 품사 집합 보관
ids, docs, metas = [], [], []
for path in files:
    with open(path, encoding="utf-8") as f:
        item = json.load(f)

    # 질문(question)이 없으면 스킵
    if not item.get("question"):
        print(f"⚠️  Skip {path} (missing question)")
        continue

    ids.append(item["id"])  # 고유 ID는 기존 JSON의 id 사용
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
    # 읽기 난이도
    clean_meta["reading_level"] = readability_kor(passage_text)
    # ― 그룹 해시 추가 ―
    clean_meta["group"] = passage_hash(item)
    # 원본 JSON 파일 경로 저장
    clean_meta["file_path"] = path
    metas.append(clean_meta)

# ── ❺ 임베딩 함수 (로컬) ─────────────────────

def embed(batch, batch_size: int = 64):
    """SentenceTransformer(≤256 tokens) CPU 임베딩 → list[list[float]] 반환"""
    vecs = _model.encode(
        batch,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vecs.tolist()

# ── ❻ 임베딩 (청크‑평균) ─────────────────────
embs = []
for idx, doc in enumerate(docs, 1):
    chunks = chunk_text(doc, MAX_TOK)
    chunk_vecs = embed(chunks, batch_size=4)  # 소청크 배치
    # 평균 풀링
    avg_vec = np.mean(chunk_vecs, axis=0).tolist()
    embs.append(avg_vec)
    if idx % 20 == 0 or idx == len(docs):
        print(f"  → Embedded {idx}/{len(docs)} docs ({len(chunks)} chunks last)")

# ── ❼ 의미·형식 최대 유사도 계산 ───────────
max_sem_sims = []
max_struct_sims = []

for i, emb_i in enumerate(embs):
    if i == 0:  # 첫 항목은 자기 자신뿐
        max_sem_sims.append(1.0)
        max_struct_sims.append(1.0)
        continue

    sem_scores = [cosine_sim(emb_i, embs[j]) for j in range(i)]
    struct_scores = [pos_jaccard(pos_sets[i], pos_sets[j]) for j in range(i)]

    max_sem_sims.append(max(sem_scores))
    max_struct_sims.append(max(struct_scores))

# 메타데이터에 유사도 기록
for i, meta in enumerate(metas):
    meta["max_sem_sim"] = round(max_sem_sims[i], 4)
    meta["max_struct_sim"] = round(max_struct_sims[i], 4)

# ── ❽ Chroma 컬렉션에 저장 ───────────────────
col.add(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
print(f"✅  {len(ids)} items stored in {DB_PATH}:{COL_NAME}")