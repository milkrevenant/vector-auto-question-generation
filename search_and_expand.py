import chromadb, re, os, json

from openai import OpenAI
import openai

openai.api_key = os.environ.get("OPENAI_API_KEY")

def generate_with_openai(new_passage, template_questions, n_questions=5):
    system = "You are a Korean CSAT question writer. Given example questions, create new ones for the new passage."
    user_prompt = f"""
새 지문:
\"\"\"{new_passage}\"\"\"

예시 문제들:
{chr(10).join(f"- {q}" for q in template_questions)}

위 예시를 참고하여 새로운 지문에 맞는 문제 {n_questions}개를 만들어주세요.
"""
    resp = cli.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=800,
    )
    text = resp.choices[0].message.content
    return [line.strip(" -") for line in text.splitlines() if line.strip()]


DB = "./sn_csat.db"; COL = "sn_csat_openai"
EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-large")
TOP_K = 50                  # HNSW 1차 후보 (더 많은 후보 검색)
GROUP_PICK = 2              # 지문 2개 선택


cli = OpenAI()
col = chromadb.PersistentClient(path=DB).get_collection(COL)

def embed(text):
    return cli.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding

def extract_group(doc_id: str):
    # 예: 23_11_37_2  →  23_11_37
    m = re.match(r"(\d{2}_\d{2}_\d{2})_", doc_id)
    return m.group(1) if m else doc_id

 # 0) 지문 유형 선택
categories = ["문학", "독서", "화법", "작문", "언어", "매체"]
print("지문 유형을 선택하세요:")
for idx, cat in enumerate(categories, 1):
    print(f"{idx}. {cat}")
sel = input("번호 또는 유형명을 입력하세요 (예: 1 또는 문학): ").strip()
if sel.isdigit() and 1 <= int(sel) <= len(categories):
    type_choice = categories[int(sel)-1]
elif sel in categories:
    type_choice = sel
else:
    type_choice = ""
    print("잘못된 입력이거나 선택되지 않아 전체 유형으로 진행합니다.")
print(f"선택된 지문 유형: {type_choice or '전체'}")

# 1) 새 지문 입력: 파일 경로 또는 직접 입력
input_choice = input("📝 지문 입력 방식을 선택하세요:\n1. 파일 경로 입력\n2. 직접 텍스트 입력\n선택 (1 또는 2): ").strip()

if input_choice == "1":
    file_path = input("📁 지문 파일 경로를 입력하세요:\n").strip()
    
    # 파일 확장자에 따라 처리
    import subprocess
    import os
    
    if file_path.endswith('.rtf'):
        # RTF 파일 처리
        result = subprocess.run(['textutil', '-convert', 'txt', '-stdout', file_path], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            query = result.stdout
        else:
            print("RTF 파일 변환 중 오류 발생")
            raise Exception("RTF 파일 변환 실패")
    
    elif file_path.endswith('.docx'):
        # DOCX 파일 처리 (python-docx 필요)
        try:
            from docx import Document
            doc = Document(file_path)
            query = '\n'.join([para.text for para in doc.paragraphs if para.text])
        except ImportError:
            print("DOCX 파일을 읽으려면 python-docx를 설치하세요: pip install python-docx")
            raise
    
    elif file_path.endswith('.pdf'):
        # PDF 파일 처리 (pypdf 필요)
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                query = ''
                for page in pdf_reader.pages:
                    query += page.extract_text()
        except ImportError:
            print("PDF 파일을 읽으려면 PyPDF2를 설치하세요: pip install PyPDF2")
            raise
    
    elif file_path.endswith(('.txt', '.md')):
        # 텍스트 파일 처리
        with open(file_path, encoding="utf-8") as f:
            query = f.read()
    
    else:
        # 기타 파일은 텍스트로 시도
        try:
            with open(file_path, encoding="utf-8") as f:
                query = f.read()
        except UnicodeDecodeError:
            print(f"지원하지 않는 파일 형식입니다: {os.path.splitext(file_path)[1]}")
            raise

elif input_choice == "2":
    print("📝 지문을 입력하세요 (입력 완료 후 빈 줄을 두 번 입력):")
    lines = []
    empty_count = 0
    while True:
        line = input()
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
        else:
            empty_count = 0
            lines.append(line)
    query = '\n'.join(lines)

else:
    print("잘못된 선택입니다. 프로그램을 종료합니다.")
    exit()

print(f"\n읽어온 지문 (처음 200자):\n{query[:200]}...")
q_vec = embed(query)

hits = col.query(query_embeddings=[q_vec], n_results=TOP_K)
ids    = hits["ids"][0]
metas  = hits["metadatas"][0]

# 디버깅: 메타데이터에서 독서 유형 확인
doksu_count = sum(1 for meta in metas if meta.get("type") == "독서")
print(f"\n디버깅: 전체 {len(metas)}개 후보 중 '독서' 유형: {doksu_count}개")

# 1) 유사 지문 후보 표시 및 그룹 선택 (선택된 유형 필터링)
distances = hits["distances"][0]
# 후보 중 선택된 유형만 필터링
if type_choice:
    candidates = [(doc_id, meta, dist) for doc_id, meta, dist in zip(ids, metas, distances)
                  if meta.get("type") == type_choice]
    if not candidates:
        print(f"선택된 유형 '{type_choice}'에 해당하는 후보가 없습니다. 전체 후보로 진행합니다.")
        candidates = list(zip(ids, metas, distances))
else:
    candidates = list(zip(ids, metas, distances))
# 거리 -> 유사도 변환 및 정렬 (높은 유사도 순), 상위 8개만
candidates_sim = [(doc_id, meta, dist, 1 - dist) for doc_id, meta, dist in candidates]
candidates_sorted = sorted(candidates_sim, key=lambda x: x[3], reverse=True)[:8]
print("\n▶ 유사 지문 후보 (상위 8개, 높은 유사도 순):")
for idx, (_id, meta, dist, sim) in enumerate(candidates_sorted, 1):
    snippet = col.get(where={"id": _id})["documents"][0][:100].replace("\n", " ")
    print(f"{idx}. ID: {_id}, 유형: {meta.get('type')}, 유사도: {sim:.4f} (거리: {dist:.4f})")
    print(f"   미리보기: {snippet}...")
selection = input("원하는 지문 번호를 쉼표로 구분하여 입력하세요 (예: 1,2):\n").strip()
chosen_idxs = [int(i) - 1 for i in selection.split(",") if i.strip().isdigit()]
uniq_groups = []
for i in chosen_idxs:
    _id = candidates_sorted[i][0]
    g = extract_group(_id)
    if g not in uniq_groups:
        uniq_groups.append(g)
print("\n선택된 지문 그룹:", uniq_groups)

# 2) 각 그룹에 속한 모든 문제 세트 가져오기
all_sets = []
for g in uniq_groups:
    where_filter = {"group": g}
    group_docs = col.get(where=where_filter)
    for doc, meta in zip(group_docs["documents"], group_docs["metadatas"]):
        all_sets.append({"meta": meta, "doc": doc})

 # — 검증 단계: 추출된 원본 문제 세트 확인 —
old_questions = [s["meta"].get("question") for s in all_sets if s["meta"].get("question")]
print("\n>>> 추출된 원본 문제 세트:")
for idx, q in enumerate(old_questions, 1):
    print(f"{idx}. {q}")
input("\n위 문제 세트가 맞으면 엔터를 눌러주세요…")

# 4) 새로운 문제 생성
new_questions = generate_with_openai(query, old_questions, n_questions=5)
print("\n▶ 새롭게 생성된 문제:")
for idx, nq in enumerate(new_questions, 1):
    print(f"{idx}. {nq}")

# 3) 보기 좋게 출력
for i, s in enumerate(all_sets, 1):
    print(f"\n=== 세트 {i} / 그룹 {extract_group(s['meta']['id'])} ===")
    print(s["doc"][:800], "..." if len(s["doc"]) > 800 else "")
