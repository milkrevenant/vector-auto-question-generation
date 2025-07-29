import os
import json
import pdfplumber
import re
from typing import Dict, List, Optional, Tuple
import glob

class ExamProcessor:
    def __init__(self):
        self.passages = {}  # 지문 저장용
        self.questions = {}  # 문제 저장용
        
    def extract_all_text(self, pdf_dir: str) -> Dict[int, str]:
        """모든 PDF 페이지에서 텍스트 추출"""
        all_text = {}
        pdf_files = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
        
        for pdf_file in pdf_files:
            page_num = int(re.search(r'page(\d+)', pdf_file).group(1))
            with pdfplumber.open(pdf_file) as pdf:
                page = pdf.pages[0]
                all_text[page_num] = page.extract_text()
                
        return all_text
    
    def find_passages_and_questions(self, all_text: Dict[int, str]):
        """지문과 문제 찾기"""
        # 지문 마커 패턴
        passage_pattern = r'\[(\d+)\s*[~∼]\s*(\d+)\]'
        
        # 모든 페이지를 통합해서 처리
        combined_text = ""
        for page_num in sorted(all_text.keys()):
            combined_text += f"\n===PAGE{page_num}===\n" + all_text[page_num]
        
        # 지문 찾기
        current_passage = None
        current_passage_nums = []
        current_passage_text = ""
        
        lines = combined_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 페이지 마커 확인
            page_match = re.match(r'===PAGE(\d+)===', line)
            if page_match:
                current_page = int(page_match.group(1))
                i += 1
                continue
            
            # 지문 마커 찾기
            passage_match = re.search(passage_pattern, line)
            if passage_match:
                # 이전 지문 저장
                if current_passage_nums:
                    for num in current_passage_nums:
                        self.passages[num] = current_passage_text.strip()
                
                # 새 지문 시작
                start_num = int(passage_match.group(1))
                end_num = int(passage_match.group(2))
                current_passage_nums = list(range(start_num, end_num + 1))
                current_passage_text = ""
                i += 1
                continue
            
            # 문제 번호 찾기
            question_match = re.match(r'^(\d{1,2})\s*\.\s*(.+)', line)
            if question_match:
                q_num = int(question_match.group(1))
                q_text = question_match.group(2)
                
                # 지문 저장
                if current_passage_nums and q_num in current_passage_nums:
                    for num in current_passage_nums:
                        self.passages[num] = current_passage_text.strip()
                    current_passage_nums = []
                    current_passage_text = ""
                
                # 문제 및 선택지 처리
                question_lines = [q_text]
                j = i + 1
                
                # 선택지 찾기
                options = []
                while j < len(lines) and len(options) < 5:
                    opt_line = lines[j]
                    
                    # 다음 문제나 지문이 나오면 중단
                    if re.match(r'^\d{1,2}\s*\.', opt_line) or re.search(passage_pattern, opt_line):
                        break
                    
                    # 선택지 패턴
                    for idx, marker in enumerate(['①', '②', '③', '④', '⑤']):
                        if marker in opt_line:
                            # 해당 선택지부터 다음 선택지까지 추출
                            option_text = opt_line
                            k = j + 1
                            while k < len(lines):
                                next_line = lines[k]
                                # 다음 선택지나 문제가 나오면 중단
                                if any(m in next_line for m in ['①', '②', '③', '④', '⑤']) or re.match(r'^\d{1,2}\s*\.', next_line):
                                    break
                                option_text += " " + next_line.strip()
                                k += 1
                            
                            # 선택지 번호 제거 및 정리
                            option_text = re.sub(r'[①②③④⑤]', '', option_text).strip()
                            options.append({
                                "number": idx + 1,
                                "text": ' '.join(option_text.split())
                            })
                    
                    j += 1
                
                # 문제 저장
                self.questions[q_num] = {
                    "question": q_text,
                    "options": options
                }
                
                i = j - 1
            
            # 지문 텍스트 추가
            elif current_passage_nums:
                current_passage_text += line + "\n"
            
            i += 1
        
        # 마지막 지문 저장
        if current_passage_nums:
            for num in current_passage_nums:
                self.passages[num] = current_passage_text.strip()
    
    def create_json_files(self, output_dir: str):
        """각 문제별로 JSON 파일 생성"""
        for q_num, q_data in sorted(self.questions.items()):
            # 지문 찾기
            passage = self.passages.get(q_num, "")
            
            # 문제 유형 판단
            if 1 <= q_num <= 9:
                type_str = "독서"
            elif 10 <= q_num <= 34:
                type_str = "문학/비문학"
            else:
                type_str = "화법과 작문"
            
            # JSON 데이터 구성
            json_data = {
                "id": f"25_11_{q_num:02d}",
                "source": "2025학년도 대학수학능력시험",
                "year": 2025,
                "month": 11,
                "exam_type_code": 0,  # 수능
                "subject_code": "03",  # 국어
                "type": type_str,
                "passage": passage,
                "context_box": "",
                "question": q_data["question"],
                "options": q_data["options"],
                "answer_rate": 0,
                "difficulty": ""
            }
            
            # 파일 저장
            output_file = os.path.join(output_dir, f"25_11_{q_num:02d}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            print(f"Created: {output_file}")

def main():
    processor = ExamProcessor()
    
    # PDF 텍스트 추출
    pdf_dir = "pdforg/25_11_split"
    all_text = processor.extract_all_text(pdf_dir)
    
    # 지문과 문제 찾기
    processor.find_passages_and_questions(all_text)
    
    # JSON 파일 생성
    output_dir = "db"
    processor.create_json_files(output_dir)
    
    print(f"\nTotal passages found: {len(processor.passages)}")
    print(f"Total questions found: {len(processor.questions)}")

if __name__ == "__main__":
    main()