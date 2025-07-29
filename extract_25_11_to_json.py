import os
import json
import pdfplumber
import re
from typing import Dict, List, Optional, Tuple

class ExamTextExtractor:
    def __init__(self):
        self.question_patterns = [
            r'^(\d{1,2})\.\s*(.+)',  # 1. 문제
            r'^(\d{1,2})\s+(.+)',      # 1 문제 (점 없이)
        ]
        self.choice_patterns = [
            r'①', r'②', r'③', r'④', r'⑤',  # ○형 숫자
            r'\(1\)', r'\(2\)', r'\(3\)', r'\(4\)', r'\(5\)'  # (1) 형태
        ]
        self.passage_markers = r'\[(\d+)\s*~\s*(\d+)\]'  # [지문번호]
        
    def extract_text_from_page(self, pdf_path: str) -> str:
        """PDF 페이지에서 텍스트 추출"""
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            return page.extract_text()
    
    def is_two_column_layout(self, text: str) -> bool:
        """2단 레이아웃인지 확인"""
        lines = text.split('\n')
        # 중간에 큰 공백이 있는 라인이 많으면 2단
        large_gap_count = 0
        for line in lines[:20]:  # 처음 20줄만 확인
            if '       ' in line:  # 7개 이상의 공백
                large_gap_count += 1
        return large_gap_count > 5
    
    def parse_question(self, text: str) -> Optional[Dict]:
        """문제 파싱"""
        lines = text.strip().split('\n')
        if not lines:
            return None
            
        # 문제 번호 찾기
        question_num = None
        question_text = None
        
        for pattern in self.question_patterns:
            match = re.match(pattern, lines[0])
            if match:
                question_num = int(match.group(1))
                question_text = match.group(2)
                break
        
        if not question_num:
            return None
            
        # 선택지 찾기
        options = []
        option_texts = []
        
        # 전체 텍스트에서 선택지 찾기
        full_text = '\n'.join(lines[1:])
        
        # ○형 숫자 찾기
        for i, marker in enumerate(['①', '②', '③', '④', '⑤']):
            pattern = f'{marker}\s*(.+?)(?=[①②③④⑤]|$)'
            match = re.search(pattern, full_text, re.DOTALL)
            if match:
                option_text = match.group(1).strip()
                option_text = ' '.join(option_text.split())  # 공백 정리
                options.append({
                    "number": i + 1,
                    "text": option_text
                })
        
        # (1) 형태 선택지 찾기 (○형이 없을 경우)
        if not options:
            for i in range(1, 6):
                pattern = f'\({i}\)\s*(.+?)(?=\({i+1}\)|$)'
                match = re.search(pattern, full_text, re.DOTALL)
                if match:
                    option_text = match.group(1).strip()
                    option_text = ' '.join(option_text.split())
                    options.append({
                        "number": i,
                        "text": option_text
                    })
        
        return {
            "number": question_num,
            "question": question_text,
            "options": options
        }
    
    def extract_passage(self, text: str) -> Optional[str]:
        """지문 추출"""
        # [지문번호] 패턴 찾기
        marker_match = re.search(self.passage_markers, text)
        if not marker_match:
            return None
            
        # 마커 이후의 텍스트 추출
        marker_pos = marker_match.end()
        passage_text = text[marker_pos:].strip()
        
        # 다음 문제 번호가 나오는 부분까지만 추출
        next_question_match = re.search(r'\n\d{1,2}[\.\s]', passage_text)
        if next_question_match:
            passage_text = passage_text[:next_question_match.start()]
        
        return passage_text.strip()
    
    def process_page(self, pdf_path: str, page_num: int) -> List[Dict]:
        """페이지 처리하여 JSON 데이터 생성"""
        text = self.extract_text_from_page(pdf_path)
        if not text:
            return []
        
        results = []
        
        # 지문과 문제를 분리
        sections = re.split(r'\n(?=\d{1,2}[\.\s])', text)
        
        current_passage = None
        
        for section in sections:
            # 지문 확인
            passage = self.extract_passage(section)
            if passage:
                current_passage = passage
                continue
                
            # 문제 파싱
            question_data = self.parse_question(section)
            if question_data:
                # JSON 형식에 맞게 구성
                json_data = {
                    "id": f"25_11_{question_data['number']:02d}",
                    "source": "2025학년도 11월 대학수학능력시험",
                    "year": 2025,
                    "month": 11,
                    "exam_type_code": 0,  # 수능
                    "subject_code": "03",  # 국어
                    "type": "",  # 나중에 채우기
                    "passage": current_passage if current_passage else "",
                    "context_box": "",
                    "question": question_data['question'],
                    "options": question_data['options'],
                    "answer_rate": 0,
                    "difficulty": ""
                }
                results.append(json_data)
        
        return results

def main():
    extractor = ExamTextExtractor()
    
    # 처리할 PDF 파일들
    pdf_dir = "pdforg/25_11_split"
    output_dir = "db"
    
    all_questions = []
    
    for i in range(1, 21):  # 20페이지
        pdf_file = os.path.join(pdf_dir, f"25_11_page{i:02d}.pdf")
        if os.path.exists(pdf_file):
            print(f"Processing {pdf_file}...")
            questions = extractor.process_page(pdf_file, i)
            all_questions.extend(questions)
    
    # 중복 제거 및 정렬
    unique_questions = {}
    for q in all_questions:
        unique_questions[q['id']] = q
    
    # JSON 파일로 저장
    for q_id, q_data in sorted(unique_questions.items()):
        output_file = os.path.join(output_dir, f"{q_id}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(q_data, f, ensure_ascii=False, indent=2)
        print(f"Created: {output_file}")
    
    print(f"\nTotal questions extracted: {len(unique_questions)}")

if __name__ == "__main__":
    main()