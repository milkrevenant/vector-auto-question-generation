import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import chromadb
import re
import os
import json
from openai import OpenAI
import subprocess
from sentence_transformers import SentenceTransformer
import numpy as np

# 상수 정의
DB = "./sn_csat_2.db"          # 새 DB
COL = "sn_csat_openai"
LOCAL_MODEL = os.environ.get("LOCAL_EMBED_MODEL", "nlpai-lab/KURE-v1")
TOP_K = 50
GROUP_PICK = 2

# 전역 변수
cli = None
col = None

# 첫 호출 시 로컬 모델 로드 (CPU)
_local_st = None
def _get_local_model():
    global _local_st
    if _local_st is None:
        _local_st = SentenceTransformer(LOCAL_MODEL, device="cpu")
        try:
            _local_st.max_seq_length = 256
        except AttributeError:
            pass
    return _local_st

def embed(text: str):
    """
    로컬 SentenceTransformer(KURE‑v1) 임베딩만 사용 (1024‑dim)
    OpenAI 경로는 제거하여 Chroma 컬렉션(동일 차원)과 일관성 유지.
    """
    st = _get_local_model()
    return st.encode(text, normalize_embeddings=True).tolist()

def extract_group(doc_id: str):
    m = re.match(r"(\d{2}_\d{2}_\d{2})_", doc_id)
    return m.group(1) if m else doc_id

def load_question_from_meta(meta: dict):
    """
    meta['file_path']를 열어 (질문 + 선택지) 하나의 문자열 반환.
    실패 시 None.
    """
    try:
        fp = meta.get("file_path")
        if not fp or not os.path.exists(fp):
            return None
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        q = data.get("question", "")
        opts = data.get("options", [])
        if not q:
            return None
        opt_str = " ".join(f"{opt.get('number')}. {opt.get('text')}" for opt in opts)
        return f"{q}  {opt_str}"
    except Exception:
        return None

def extract_marker_map(text: str, window: int = 25):
    """
    지문에서 ㉠, ㉡, ㉢, ⓐ~ⓔ 등 특수 표지와 주변 단어를 추출해
    {marker: snippet} dict 반환.
    window: 앞뒤 글자 수
    """
    markers = re.findall(r"[㉠-㉿ⓐ-ⓔ]", text)
    uniq = list(dict.fromkeys(markers))  # preserve order
    mapping = {}
    for m in uniq:
        for match in re.finditer(re.escape(m), text):
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            snippet = text[start:end].replace("\n", " ")
            mapping[m] = snippet
            break  # 첫 위치만
    return mapping

def generate_with_openai(new_passage, template_questions, marker_map, n_questions=5):
    """
    marker_map: dict like {'㉠': '...', 'ⓐ': '...'} to include in prompt.
    """
    system = ("You are a Korean CSAT question writer.\n"
          "• Output up to four problems.\n"
          "• Each problem must display exactly 5 answer choices numbered ① ② ③ ④ ⑤.\n"
          "• If any sample includes <보기>, include at least one problem with <보기>.\n"
          "• If the sample uses ⓐ~ⓔ replace-word style, create one similar problem and wrap markers with <u>…</u>.\n"
          "• Follow the tone and length of the sample questions and return only the new problems.")
    user_prompt = f"""
새 지문:
\"\"\"{new_passage}\"\"\"

표지-문맥 정보:
{chr(10).join(f"{k}: {v}" for k,v in marker_map.items())}

예시 문제들:
{chr(10).join(f"- {q}" for q in template_questions)}

위 예시를 참고하여 새로운 지문에 맞는 문제 {n_questions}개를 만들어주세요.
"""
    resp = cli.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
    )
    text = resp.choices[0].message.content
    return [line.strip(" -") for line in text.splitlines() if line.strip()]

class SearchExpandGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("수능 지문 검색 및 문제 생성기")
        self.root.geometry("1400x900")
        
        self.selected_type = tk.StringVar(value="전체")
        self.selected_candidates = []
        self.query_text = ""
        self.api_key = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        
        self.setup_ui()
        
    def setup_ui(self):
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 왼쪽 영역 (입력)
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # 오른쪽 영역 (결과)
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # === 왼쪽 영역 구성 ===
        
        # 0. API 키 입력
        api_frame = ttk.LabelFrame(left_frame, text="API 설정", padding="5")
        api_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(api_frame, text="OpenAI API Key:").grid(row=0, column=0, padx=5)
        self.api_entry = ttk.Entry(api_frame, textvariable=self.api_key, width=40)
        self.api_entry.grid(row=0, column=1, padx=5)
        
        # API 키 보기/숨기기 체크박스
        self.show_key = tk.BooleanVar(value=False)
        show_check = ttk.Checkbutton(api_frame, text="키 표시", variable=self.show_key, 
                                    command=self.toggle_key_visibility)
        show_check.grid(row=0, column=2, padx=5)
        
        ttk.Button(api_frame, text="설정", command=self.set_api_key).grid(row=1, column=1, columnspan=2, pady=5)
        
        # 1. 지문 유형 선택
        type_frame = ttk.LabelFrame(left_frame, text="1. 지문 유형 선택", padding="5")
        type_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        categories = ["전체", "문학", "독서", "화법", "작문", "언어", "매체"]
        for i, cat in enumerate(categories):
            row = i // 4
            col = i % 4
            ttk.Radiobutton(type_frame, text=cat, variable=self.selected_type, 
                          value=cat).grid(row=row, column=col, padx=5, pady=2)

        # 1‑B. 목표 난이도 슬라이더
        level_frame = ttk.LabelFrame(left_frame, text="1‑B. 목표 난이도(0=쉬움, 1=어려움)", padding="5")
        level_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        self.target_level = tk.DoubleVar(value=0.4)
        ttk.Scale(level_frame, from_=0.0, to=1.0, orient="horizontal",
                  variable=self.target_level, length=180).grid(row=0, column=0, padx=5)
        ttk.Label(level_frame, textvariable=self.target_level, width=5).grid(row=0, column=1, padx=5)
        
        # 2. 지문 입력
        input_frame = ttk.LabelFrame(left_frame, text="2. 지문 입력", padding="5")
        input_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 파일 선택 버튼
        file_button = ttk.Button(input_frame, text="파일 선택", command=self.load_file)
        file_button.grid(row=0, column=0, padx=5, pady=5)
        
        ttk.Label(input_frame, text="또는 아래에 직접 입력:").grid(row=0, column=1, padx=5)
        
        # 텍스트 입력 영역
        self.text_input = scrolledtext.ScrolledText(input_frame, height=20, width=70)
        self.text_input.grid(row=1, column=0, columnspan=2, padx=5, pady=5)
        
        # 3. 검색 버튼
        search_button = ttk.Button(left_frame, text="유사 지문 검색", 
                                 command=self.search_similar)
        search_button.grid(row=3, column=0, pady=10)
        
        # === 오른쪽 영역 구성 ===
        
        # 4. 검색 결과 표시
        result_frame = ttk.LabelFrame(right_frame, text="3. 유사 지문 선택", padding="5")
        result_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 결과 리스트박스
        self.result_listbox = tk.Listbox(result_frame, height=15, selectmode=tk.MULTIPLE)
        self.result_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.result_listbox.config(yscrollcommand=scrollbar.set)
        
        # 미리보기
        ttk.Label(result_frame, text="미리보기:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.preview_text = scrolledtext.ScrolledText(result_frame, height=6, width=70)
        self.preview_text.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        
        # 5. 문제 생성 버튼
        generate_button = ttk.Button(result_frame, text="문제 생성", 
                                   command=self.generate_questions)
        generate_button.grid(row=3, column=0, pady=10)
        
        # 6. 생성된 문제 표시
        question_frame = ttk.LabelFrame(right_frame, text="4. 생성된 문제", padding="5")
        question_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.question_text = scrolledtext.ScrolledText(question_frame, height=20, width=70)
        self.question_text.grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 저장 버튼
        save_button = ttk.Button(question_frame, text="결과 저장", command=self.save_results)
        save_button.grid(row=1, column=0, pady=5)
        
        # 리스트박스 선택 이벤트
        self.result_listbox.bind('<<ListboxSelect>>', self.on_select)
        
        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=0)
        
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(2, weight=1)
        
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=2)
        
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        question_frame.columnconfigure(0, weight=1)
        question_frame.rowconfigure(0, weight=1)
        
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(1, weight=1)

        # ── 창 종료 버튼 (오른쪽 아래) ─────────────────────────
        exit_button = ttk.Button(main_frame, text="종료", command=self.root.quit)
        exit_button.grid(row=2, column=1, sticky=tk.E, pady=(10, 0))
        
    def toggle_key_visibility(self):
        if self.show_key.get():
            self.api_entry.config(show="")
        else:
            self.api_entry.config(show="*")
        
    def set_api_key(self):
        key = self.api_key.get().strip()
        if not key:
            messagebox.showwarning("경고", "API 키를 입력해주세요.")
            return
            
        global cli, col
        try:
            cli = OpenAI(api_key=key)
            # 연결 테스트
            cli.models.list()
            
            # ChromaDB 컬렉션 초기화
            col = chromadb.PersistentClient(path=DB).get_collection(COL)
            
            messagebox.showinfo("성공", "API 키가 설정되었습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"API 키 설정 실패: {str(e)}")
            cli = None
            col = None
    
    def load_file(self):
        file_path = filedialog.askopenfilename(
            title="지문 파일 선택",
            filetypes=[
                ("모든 텍스트 파일", "*.txt;*.rtf;*.docx;*.pdf;*.md"),
                ("텍스트 파일", "*.txt"),
                ("RTF 파일", "*.rtf"),
                ("Word 파일", "*.docx"),
                ("PDF 파일", "*.pdf"),
                ("Markdown 파일", "*.md"),
                ("모든 파일", "*.*")
            ]
        )
        
        if not file_path:
            return
            
        try:
            content = ""
            
            if file_path.endswith('.rtf'):
                result = subprocess.run(['textutil', '-convert', 'txt', '-stdout', file_path], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    content = result.stdout
                else:
                    raise Exception("RTF 파일 변환 실패")
                    
            elif file_path.endswith('.docx'):
                try:
                    from docx import Document
                    doc = Document(file_path)
                    content = '\n'.join([para.text for para in doc.paragraphs if para.text])
                except ImportError:
                    messagebox.showerror("오류", "DOCX 파일을 읽으려면 python-docx를 설치하세요.")
                    return
                    
            elif file_path.endswith('.pdf'):
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        content = ''
                        for page in pdf_reader.pages:
                            content += page.extract_text()
                except ImportError:
                    messagebox.showerror("오류", "PDF 파일을 읽으려면 PyPDF2를 설치하세요.")
                    return
                    
            else:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                    
            self.text_input.delete(1.0, tk.END)
            self.text_input.insert(1.0, content)
            
        except Exception as e:
            messagebox.showerror("오류", f"파일을 읽는 중 오류가 발생했습니다: {str(e)}")
            
    def search_similar(self):
        if not col:
            # API 없이도 로컬 검색 가능하게 컬렉션만 초기화
            try:
                client = chromadb.PersistentClient(path=DB)
                globals()["col"] = client.get_collection(COL)
            except Exception as e:
                messagebox.showerror("오류", f"ChromaDB 초기화 실패: {str(e)}")
                return
            
        self.query_text = self.text_input.get(1.0, tk.END).strip()
        
        if not self.query_text:
            messagebox.showwarning("경고", "지문을 입력해주세요.")
            return
            
        # 진행 상태 표시
        self.root.config(cursor="wait")
        self.root.update()
        
        try:
            # 임베딩 생성
            q_vec = embed(self.query_text)
            
            # 유사 지문 검색
            hits = col.query(query_embeddings=[q_vec], n_results=TOP_K)
            ids = hits["ids"][0]
            metas = hits["metadatas"][0]
            distances = hits["distances"][0]
            
            # 선택된 유형 필터링
            type_filter = self.selected_type.get()
            if type_filter != "전체":
                candidates = [(doc_id, meta, dist) for doc_id, meta, dist in zip(ids, metas, distances)
                            if meta.get("type") == type_filter]
            else:
                candidates = list(zip(ids, metas, distances))
            
            # 난이도 기반 강화 랭킹
            user_lvl = self.target_level.get()
            enhanced = []
            for doc_id, meta, dist in candidates:
                sim = 1 - dist
                diff = abs(meta.get("reading_level", 0.5) - user_lvl)
                score = 0.6 * sim - 0.3 * diff
                enhanced.append((doc_id, meta, dist, sim, score))
            # score 기준 정렬
            self.candidates_sorted = sorted(enhanced, key=lambda x: x[4], reverse=True)[:8]
            
            # 결과 표시
            self.result_listbox.delete(0, tk.END)
            for idx, (_id, meta, dist, sim, score) in enumerate(self.candidates_sorted):
                display_text = (f"{idx+1}. ID: {_id}, 유형: {meta.get('type')}, "
                                f"유사도: {sim:.3f}, 난이도: {meta.get('reading_level',0.5):.2f}")
                self.result_listbox.insert(tk.END, display_text)
                
        except Exception as e:
            messagebox.showerror("오류", f"검색 중 오류가 발생했습니다: {str(e)}")
            
        finally:
            self.root.config(cursor="")
            
    def on_select(self, event):
        selected_indices = self.result_listbox.curselection()
        if not selected_indices:
            return
            
        # 첫 번째 선택된 항목의 미리보기 표시
        idx = selected_indices[0]
        _id = self.candidates_sorted[idx][0]
        
        try:
            snippet = col.get(where={"id": _id})["documents"][0][:300].replace("\n", " ")
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, f"미리보기:\n{snippet}...")
        except:
            pass
            
    def generate_questions(self):
        if not cli or not col:
            messagebox.showwarning("경고", "먼저 API 키를 설정해주세요.")
            return
            
        selected_indices = self.result_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("경고", "유사 지문을 선택해주세요.")
            return
            
        self.root.config(cursor="wait")
        self.root.update()
        
        try:
            # 선택된 지문의 group 해시 추출 (메타에서 직접 가져오기)
            uniq_groups = []
            for i in selected_indices:
                meta_sel = self.candidates_sorted[i][1]   # 메타데이터 dict
                g = meta_sel.get("group")
                if g and g not in uniq_groups:
                    uniq_groups.append(g)

            # 각 그룹의 문제 수집
            all_sets = []
            for g in uniq_groups:
                where_filter = {"group": g}
                group_docs = col.get(where=where_filter)
                for doc, meta in zip(group_docs["documents"], group_docs["metadatas"]):
                    all_sets.append({"meta": meta, "doc": doc})

            # 원본 문제 추출 (지문 + 선택지 포함)
            old_questions = []
            for s in all_sets:
                q = load_question_from_meta(s["meta"])
                if q:
                    old_questions.append(q)

            if not old_questions:
                messagebox.showwarning("경고", "선택된 지문에서 문제를 찾을 수 없습니다.")
                return

            # marker map from first doc in group
            base_text = all_sets[0]["doc"] if all_sets else ""
            marker_map = extract_marker_map(base_text)
            # Apply HTML underline tags
            new_pass_mod = self.query_text
            for m in ["㉠","㉡","㉢","ⓐ","ⓑ","ⓒ","ⓓ","ⓔ"]:
                new_pass_mod = new_pass_mod.replace(m, f"<u>{m}</u>")
            # 새 문제 생성
            new_questions = generate_with_openai(new_pass_mod, old_questions, marker_map, n_questions=4)

            # 결과 표시
            self.question_text.delete(1.0, tk.END)
            result_text = "=== 생성된 문제 ===\n\n"
            for idx, nq in enumerate(new_questions, 1):
                # 이미 1.·2. 로 시작하면 그대로 두고, 아니면 앞에 붙임
                if re.match(r"^\d+\.", nq):
                    result_text += f"{nq}\n\n"
                else:
                    result_text += f"{idx}. {nq}\n\n"

            self.question_text.insert(1.0, result_text)

        except Exception as e:
            messagebox.showerror("오류", f"문제 생성 중 오류가 발생했습니다: {str(e)}")

        finally:
            self.root.config(cursor="")
            
    def save_results(self):
        content = self.question_text.get(1.0, tk.END).strip()
        if not content:
            messagebox.showwarning("경고", "저장할 내용이 없습니다.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"=== 입력 지문 ===\n{self.query_text}\n\n")
                    f.write(f"=== 선택된 지문 유형: {self.selected_type.get()} ===\n\n")
                    f.write(content)
                messagebox.showinfo("성공", "파일이 저장되었습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {str(e)}")

def main():
    root = tk.Tk()
    app = SearchExpandGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()