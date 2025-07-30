# 수능 지문 검색 및 문제 생성기 - 빌드 가이드

## 실행 파일로 패키징하는 방법

### 1. 필요한 패키지 설치

```bash
pip install pyinstaller
pip install chromadb openai
pip install python-docx PyPDF2  # 옵션: Word/PDF 파일 지원
```

### 2. Windows용 실행 파일 만들기

```bash
# 단일 실행 파일로 만들기
pyinstaller --onefile --windowed --name "수능문제생성기" search_and_expand_gui.py

# 또는 폴더 형태로 만들기 (더 빠른 실행)
pyinstaller --onedir --windowed --name "수능문제생성기" search_and_expand_gui.py
```

### 3. macOS용 앱 만들기

```bash
# macOS 앱 번들 생성
pyinstaller --onefile --windowed --name "수능문제생성기" --osx-bundle-identifier com.example.sn-generator search_and_expand_gui.py

# 아이콘 추가 (옵션)
pyinstaller --onefile --windowed --name "수능문제생성기" --icon=icon.icns search_and_expand_gui.py
```

### 4. 실행 전 준비사항

실행 파일과 같은 디렉토리에 다음 파일들이 있어야 합니다:
- `sn_csat.db` 폴더 (ChromaDB 데이터베이스)

### 5. 환경 변수 설정

실행 전에 OpenAI API 키를 환경 변수로 설정해야 합니다:

**Windows:**
```cmd
set OPENAI_API_KEY=your-api-key-here
```

**macOS/Linux:**
```bash
export OPENAI_API_KEY=your-api-key-here
```

### 6. 배포용 설정 파일 (선택사항)

`config.json` 파일을 만들어 설정을 관리할 수 있습니다:

```json
{
  "db_path": "./sn_csat.db",
  "collection_name": "sn_csat_openai",
  "embed_model": "text-embedding-3-large",
  "top_k": 50
}
```

### 7. 의존성 문제 해결

PyInstaller가 일부 패키지를 찾지 못할 경우:

```bash
# hidden imports 추가
pyinstaller --onefile --windowed \
  --hidden-import=chromadb \
  --hidden-import=openai \
  --name "수능문제생성기" \
  search_and_expand_gui.py
```

### 8. 빌드된 파일 위치

- Windows: `dist/수능문제생성기.exe`
- macOS: `dist/수능문제생성기.app`

### 9. 테스트

1. 빌드된 실행 파일을 새로운 폴더로 복사
2. `sn_csat.db` 폴더를 같은 위치에 복사
3. 환경 변수 설정 후 실행

### 10. 문제 해결

- **"Failed to execute script" 오류**: 콘솔 모드로 실행하여 에러 메시지 확인
  ```bash
  pyinstaller --onefile --console --name "수능문제생성기" search_and_expand_gui.py
  ```

- **ChromaDB 관련 오류**: `--collect-all chromadb` 옵션 추가

- **파일 크기가 너무 큰 경우**: UPX 압축 사용
  ```bash
  pyinstaller --onefile --windowed --upx-dir=/path/to/upx --name "수능문제생성기" search_and_expand_gui.py
  ```