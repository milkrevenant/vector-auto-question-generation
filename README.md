# vector db 기반 수능 국어 자동 문항 생성 프로그램 (연구 프로젝트) 🔬

수능 국어 문제를 Vector DB로 구축하고, 유사 문제를 검색한 뒤, 이를 바탕으로 새로운 지문에 대한 비슷한 문항을 생성하는 프로그램입니다. 향후 자동 문제 생성 기능을 개발할 예정입니다.

>  **개발 상태**: 이 프로젝트는 현재 개발 단계에 있습니다. 문항 생성 기능은 기본적으로 구현되었으며, Gemini 2.5 Pro API를 활용한 문제 생성 코드는 개발중입니다.

## 현재 구현된 기능

-  **문제 DB**: 대학수학능력시험(2023, 2024), 모의평가(2025년 6월, 9월) 문제를 JSON으로 구조화
-  **Vector 기반 검색**: ChromaDB와 OpenAI Embeddings을 활용한 유사 문제 검색
-  **검색 인터페이스**: 대화형 검색 시스템 및 확장 검색 기능
-  **연구용**: 자동 문항 생성 기능 분석을 위한 기초 프로젝트

## 개발 예정 기능 / db 변환

-  **문제 자동 생성**: 새로운 지문에 맞는 수능 스타일 문제 생성 (주요 목표)
-  **DB**종류에 따른 타당성 검증 필요(현재는 ChromaDB이지만 추후 다른 방식 필요할 수 있음.)

## 시스템 구성

### 1. 문제 데이터 추출 (수동 프로세스)
- PDF를 개별 페이지로 분할 후 Claude code를 통해 문제 추출
- JSON 형식으로 구조화하여 저장
- 각 문제별로 지문, 문제, 선택지, 정답 등 포함

### 2. 통합 처리 시스템

#### `sn_processor.py` (신규 통합 스크립트)
모든 처리 과정을 하나의 스크립트로 통합:
- **PDF 분할**: `python sn_processor.py split -i pdforg/25_11.pdf`
- **JSON 추출**: `python sn_processor.py extract -i pdforg/25_11_split --exam-year 2025 --exam-month 11`
- **DB 구축**: `python sn_processor.py build-db`
- **검색**: `python sn_processor.py search -q "검색어"`

### 3. 레거시 시스템 (기존 방식)

#### `build_sn_db.py`
- JSON 문제 데이터를 벡터 임베딩으로 변환
- OpenAI `text-embedding-3-large` 모델 사용 (3072)
- ChromaDB에 저장 (코사인 유사도 기반)

#### `search_and_expand.py`
- 벡터 데이터베이스 검색 및 확장 기능
- 검색된 문제를 기반으로 새로운 문제 생성 기능 포함
- 파일 생성이 아닌 '텍스트'형태의 데이터로만 제공(현재)

## 설치 및 사용법

### 1. 환경 설정

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일 생성:
```
OPENAI_API_KEY=your_openai_api_key
```

### 3. 데이터베이스 구축

```bash
# 벡터 DB 구축 (JSON 파일이 이미 준비되어 있음)
python build_sn_db.py
```

### 4. 사용 가능한 기능

#### 통합 스크립트 사용법 (권장)
```bash
# 1. PDF 분할
python sn_processor.py split -i pdforg/25_11.pdf

# 2. JSON 추출 (분할된 PDF에서)
python sn_processor.py extract -i pdforg/25_11_split --exam-year 2025 --exam-month 11 -o db

# 3. 데이터베이스 구축
python sn_processor.py build-db -i db

# 4. 검색
python sn_processor.py search -q "배꼽"
```

#### 레거시 방식
```bash
# 벡터 DB 구축
python build_sn_db.py

# 검색 및 문제 생성 기능
python search_and_expand.py
```


## 데이터 구조

```
snoriginal/
├── db/                      # JSON 문제 데이터
│   ├── 23_11_*.json        # 2023년 11월 수능 (45문항)
│   ├── 24_11_*.json        # 2024년 11월 수능 (45문항)
│   ├── 25_06_*.json        # 2025년 6월 모의평가 (45문항)
│   └── 25_09_*.json        # 2025년 9월 모의평가 (45문항)
├── pdforg/                  # 원본 PDF 파일 및 분할된 페이지
│   ├── 23_11.pdf
│   ├── 24_11.pdf
│   ├── 25_06.pdf
│   ├── 25_09.pdf
│   └── */split/            # 각 시험별 분할된 페이지 PDF
├── sn_processor.py         # 통합 처리 스크립트 (PDF분할, JSON추출, DB구축, 검색)
├── build_sn_db.py          # 벡터 DB 구축 스크립트 (레거시)
├── search_and_expand.py    # 확장 검색 스크립트 (레거시)
├── requirements.txt        # 필요 라이브러리
├── LICENSE                 # GPL v3.0 라이선스
├── README.md               # 프로젝트 문서
├── CLAUDE_SETUP.md         # Claude API 활용 가이드
├── sn_csat.db/             # ChromaDB 벡터 데이터베이스 (gitignore)
└── venv/                   # 가상환경 (gitignore)
```

## 문제 데이터 형식

```json
{
  "id": "24_11_05",
  "source": "2024학년도 수능 11월",
  "passage": "지문 내용...",
  "question": "문제 내용...",
  "options": [
    {"number": 1, "text": "선택지 1"},
    {"number": 2, "text": "선택지 2"},
    ...
  ],
  "correct_answer": 3,
  "difficulty": "중",
  "category": "독서",
  "subcategory": "사회"
}
```

## 특징

-  **데이터**: 수동 검증을 거친 문제 데이터이기 때문에 불완전함.
-  **검색**: ChromaDB 기반 벡터 검색
-  **임베딩**: OpenAI text-embedding-3-large  (3072)

## Requirements

- `openai`: OpenAI 임베딩 모델 및 GPT API
- `chromadb`: 벡터 데이터베이스
- `PyPDF2`: PDF 텍스트 추출 및 분할
- `tiktoken`: 토큰 계산
- `numpy`: 수치 연산
- `scikit-learn`: 머신러닝 유틸리티
- `python-dotenv`: 환경 변수 관리

# 경로 및 주의사항

- 기본 실행 방법
$ python build_sn_db.py
- ./db 폴더의 JSON을 임베딩해 ./sn_csat.db에 저장

- 경로 커스텀 필요한 부분
$ SN_SRC_DIR=/mnt/datasets/json \ 
  SN_DB_PATH=$HOME/data/sn_csat.db \
  python build_sn_db.py

- OpenAI API 키가 필요
- 생성된 문제는 검토가 반드시 필요(이건 어차피 나중에)

## 라이선스

[GNU General Public License v3.0](LICENSE)
