# vector db 기반 수능 국어 자동 문항 생성 프로그램 (연구 프로젝트) 🔬

수능 국어 문제를 Vector DB로 구축하고, 유사 문제를 검색한 뒤, 이를 바탕으로 새로운 지문에 대한 비슷한 문항을 생성하는 프로그램입니다. 향후 자동 문제 생성 기능을 개발할 예정입니다.

>  **개발 상태**: 이 프로젝트는 현재 개발 단계에 있습니다. 문항 자동 생성은 아직입니다.

## 현재 구현된 기능

-  **PDF 분할**: 수능 PDF를 페이지별로 분할
-  **문제 DB**: 2023-2025년 수능 문제를 JSON으로 구조화
-  **Vector 기반 검색**: ChromaDB와 OpenAI Embeddings를 활용한 유사 문제 검색
-  **연구 기반**: 자동 문항 생성 기능 분석을 위한 기초 프로젝트

## 개발 예정 기능 🚧

-  **문제 자동 생성**: 새로운 지문에 맞는 수능 스타일 문제 생성 (주요 목표)

## 시스템 구성

### 1. PDF 처리 파이프라인

#### `split_pdf.py` / `split_pdf_single_pages.py`
- 수능 PDF를 페이지별로 분할
- 문제별 개별 PDF 생성

#### 문제 데이터 추출 (수동 프로세스)
- PDF를 개별 페이지로 분할 후 Claude code를 통해 문제 추출
- JSON 형식으로 구조화하여 저장
- 각 문제별로 지문, 문제, 선택지, 정답 등 포함

### 2. Vector DB 생성

#### `build_sn_db.py`
- JSON 문제 데이터를 벡터 임베딩으로 변환
- OpenAI `text-embedding-3-large` 모델 사용 (3072)
- ChromaDB에 저장 (코사인 유사도 기반)

#### `query_sn_db.py`
- 벡터 데이터베이스 검색 인터페이스
- 유사 문제 검색 및 분석
- 대화형 검색 지원

### 3. 문제 생성 시스템 (향후 개발 예정)

#### `auto_question_generator.py` (미구현, 파일 이름 바뀔 수 있음.)
- **계획된 기능**:
  - 새로운 지문 입력 → 유사 문제 검색
  - 문제 패턴 분석 (유형, 난이도, 형식)
  - LLM과 검색된 문항을 통한 문제 생성
- **현재 상태**: 파일이 아직 생성되지 않음

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

```bash
# 벡터 검색 테스트 (현재 사용 가능)
python query_sn_db.py
```

### 5. 개발 예정 기능

```bash
# 문제 자동 생성 (아직 구현되지 않음)
# python auto_question_generator.py  # 향후 개발 예정
```

## 데이터 구조

```
snoriginal/
├── db/                      # JSON 문제 데이터
│   ├── 23_11_*.json        # 2023년 11월 수능
│   ├── 24_11_*.json        # 2024년 11월 수능
│   └── 25_06_*.json        # 2025년 6월 모의평가
├── pdforg/                  # 원본 PDF 파일
│   ├── 23_11.pdf
│   ├── 24_11.pdf
│   └── 25_06.pdf
├── build_sn_db.py          # 벡터 DB 구축 스크립트
├── query_sn_db.py          # 벡터 검색 스크립트
├── split_pdf*.py           # PDF 분할 스크립트
├── requirements.txt        # 필요 라이브러리
├── LICENSE                 # GPL v3.0 라이선스
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

-  **연구 중심**: 수능 문제 패턴 분석을 위한 기초 연구 프로젝트
-  **데이터**: 수동 검증을 거친 정확한 문제 데이터
-  **검색**: ChromaDB의 효율적인 벡터 검색
-  **임베딩**: OpenAI text-embedding-3-large 모델 (3072차원)

## Requirements

- `openai`: OpenAI 임베딩 모델 및 GPT API
- `chromadb`: 벡터 데이터베이스
- `pypdfium2`: PDF 이미지 변환
- `PyPDF2`: PDF 텍스트 추출
- `tiktoken`: 토큰 계산
- `python-dotenv`: 환경 변수 관리

## 주의사항

- OpenAI API 키가 필요합니다
- 생성된 문제는 검토가 반드시 필요합니다.

## 라이선스

[GNU General Public License v3.0](LICENSE)]