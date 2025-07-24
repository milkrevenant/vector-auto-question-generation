# 수능 국어 문제 자동 생성 시스템

PDF 형식의 수능 국어 문제를 분석하여 벡터 데이터베이스를 구축하고, 새로운 지문에 맞는 문제를 자동으로 생성하는 AI 시스템입니다.

## 주요 기능

- 📄 **PDF 문제 추출**: 수능 PDF에서 문제 데이터를 자동 추출
- 🔍 **벡터 검색**: ChromaDB와 OpenAI Embeddings를 활용한 의미 기반 검색
- 🤖 **문제 자동 생성**: 새로운 지문에 맞는 수능 스타일 문제 생성
- 📊 **다년도 데이터**: 2023-2025년 수능 문제 데이터베이스

## 시스템 구성

### 1. PDF 처리 파이프라인

#### `split_pdf.py` / `split_pdf_single_pages.py`
- 수능 PDF를 페이지별로 분할
- 문제별 개별 PDF 생성

#### 문제 데이터 추출 (수동 프로세스)
- PDF를 개별 페이지로 분할 후 Claude를 통해 문제 추출
- JSON 형식으로 구조화하여 저장
- 각 문제별로 지문, 문제, 선택지, 정답 등 포함

### 2. 벡터 데이터베이스

#### `build_sn_db.py`
- JSON 문제 데이터를 벡터 임베딩으로 변환
- OpenAI `text-embedding-3-large` 모델 사용 (3072차원)
- ChromaDB에 저장 (코사인 유사도 기반)
- 128개씩 배치 처리로 API 효율성 최적화

#### `query_sn_db.py`
- 벡터 데이터베이스 검색 인터페이스
- 유사 문제 검색 및 분석
- 대화형 검색 지원

### 3. 문제 생성 시스템

#### `auto_question_generator.py` (개발 중 🚧)
- 새로운 지문 입력 → 유사 문제 검색
- 문제 패턴 분석 (유형, 난이도, 형식)
- AI 프롬프트 자동 생성
- GPT-4o를 통한 문제 생성 (구현 예정)

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

### 4. 문제 생성

```bash
# 벡터 검색 테스트
python query_sn_db.py

# 문제 생성 (개발 중)
# python auto_question_generator.py
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
├── sn_csat.db/             # ChromaDB 벡터 데이터베이스
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

- ✅ **높은 정확도**: 수동 검증을 거친 정확한 문제 데이터
- 🚀 **빠른 검색**: ChromaDB의 효율적인 벡터 검색
- 🎯 **패턴 학습**: 기존 문제 패턴을 분석하여 일관된 스타일 유지
- 📈 **확장 가능**: 새로운 PDF 추가 시 동일한 프로세스로 처리 가능
- 🔍 **고성능 임베딩**: OpenAI text-embedding-3-large 모델 (3072차원)로 정확한 의미 파악

## 주요 의존성

- `openai`: OpenAI 임베딩 모델 및 GPT API
- `chromadb`: 벡터 데이터베이스
- `pypdfium2`: PDF 이미지 변환
- `PyPDF2`: PDF 텍스트 추출
- `tiktoken`: 토큰 계산
- `python-dotenv`: 환경 변수 관리

## 주의사항

- OpenAI API 키가 필요합니다
- 대용량 PDF 처리 시 API 비용이 발생할 수 있습니다
- 생성된 문제는 검토 후 사용을 권장합니다

## 라이선스

이 프로젝트는 [GNU General Public License v3.0](LICENSE)에 따라 라이선스가 부여됩니다.

이는 다음을 의미합니다:
- ✅ 상업적 사용 가능
- ✅ 수정 가능
- ✅ 배포 가능
- ✅ 특허 사용 가능
- ⚠️ 동일한 라이선스로 배포해야 함
- ⚠️ 소스 코드 공개 의무
- ❌ 책임 제한
- ❌ 보증 없음