@echo off
echo 수능 문제 생성기를 시작합니다...

REM OpenAI API 키 설정 (여기에 실제 API 키를 입력하세요)
set OPENAI_API_KEY=your-api-key-here

REM Python 실행
python search_and_expand_gui.py

pause