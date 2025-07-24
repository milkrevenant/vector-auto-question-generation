# 수능 국어 문제 생성 시스템

이 시스템은 기존 수능 국어 문제들을 벡터 데이터베이스로 구축하고, 새로운 지문을 입력받아 유사한 문제들을 찾아 새로운 문제를 생성하는 AI 기반 시스템입니다.

## 구성 요소

### 1. 데이터 구조
- `db/` 폴더: JSON 형식의 수능 문제 데이터 (34개 문제)
  - 문제 ID, 출처, 유형, 지문, 문제, 선택지 등을 포함
  - 2023학년도 수능 11월 시행분 5번~34번 문제

### 2. 핵심 스크립트

#### `embed_json.py`
- JSON 파일들을 읽어 벡터 임베딩으로 변환
- Snowflake Arctic Embed L v2.0 모델 사용
- 임베딩 결과를 `embeddings.pkl`에 저장

#### `search_embeddings.py` 
- 벡터 검색 기능 제공
- 키워드 검색으로 유사한 문제들을 찾아줌
- 대화형 인터페이스 지원

#### `question_generator.py`
- 메인 문제 생성 시스템
- 새로운 지문을 입력받아 유사한 문제들을 검색
- 문제 패턴을 분석하고 AI 프롬프트를 생성

### 3. 테스트 스크립트
- `test_question_gen.py`: 문제 생성 시스템 테스트
- `test_search.py`: 벡터 검색 시스템 테스트

## 사용 방법

### 1. 의존성 설치
```bash
pip install sentence-transformers torch numpy scikit-learn
```

### 2. 벡터 DB 생성
```bash
python3 embed_json.py
```

### 3. 문제 생성 테스트
```bash
python3 test_question_gen.py
```

### 4. 검색 시스템 테스트
```bash
python3 test_search.py
```

### 5. 대화형 문제 생성
```bash
python3 question_generator.py
```

## 시스템 동작 방식

1. **지문 입력**: 사용자가 새로운 지문을 입력
2. **유사도 검색**: 벡터 임베딩을 통해 기존 문제들과의 유사도 계산
3. **패턴 분석**: 상위 유사 문제들의 유형, 형식, 난이도 패턴 추출
4. **프롬프트 생성**: AI가 새로운 문제를 만들 수 있는 상세한 프롬프트 생성
5. **결과 출력**: 생성된 프롬프트를 파일로 저장하여 ChatGPT/Claude 등에서 사용 가능

## 특징

- **정확한 유사도 검색**: Snowflake Arctic Embed L v2.0 모델로 의미적 유사도 계산
- **패턴 기반 생성**: 기존 문제들의 패턴을 학습하여 일관된 형식의 문제 생성
- **다양한 문제 유형 지원**: 독서, 문학, 언어와 매체 등 다양한 유형 처리
- **CPU 최적화**: 메모리 효율적인 배치 처리로 안정적인 실행

## 파일 구조
```
/Users/stillclie_mac/Documents/ug/snoriginal/
├── db/                    # JSON 문제 데이터
│   ├── 23_11_01.json
│   ├── 23_11_02.json
│   └── ... (총 34개)
├── embed_json.py          # 벡터 임베딩 생성
├── search_embeddings.py   # 벡터 검색 시스템
├── question_generator.py  # 문제 생성 시스템
├── test_question_gen.py   # 문제 생성 테스트
├── test_search.py         # 검색 테스트
├── embeddings.pkl         # 생성된 벡터 DB
├── ai_prompt.txt          # 생성된 AI 프롬프트
└── requirements.txt       # 의존성 목록
```

## 성능 확인

테스트 결과, 시스템은 다음과 같은 성능을 보입니다:
- 34개 문제에 대한 벡터 DB 구축 완료
- 의미적 유사도 기반 정확한 검색 (예: "법령과 행정" 검색 시 관련 문제들 정확히 검색)
- 문제 유형별 패턴 분석 (독서, 문학, 어법 등)
- AI 프롬프트 자동 생성으로 새로운 문제 생성 지원

이 시스템을 통해 교육자들은 새로운 지문에 대해 기존 수능 문제 패턴을 따르는 고품질 문제를 효율적으로 생성할 수 있습니다.