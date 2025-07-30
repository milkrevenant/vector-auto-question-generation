#!/usr/bin/env python3
"""
수능 국어 PDF 처리 통합 스크립트
- PDF 분할
- 텍스트 추출
- JSON 데이터베이스 생성
- 데이터베이스 검색 및 분석
"""

import os
import sys
import json
import re
import argparse
from typing import Dict, List, Optional, Tuple
import glob

# PDF 처리 관련
import PyPDF2
import pdfplumber

# 데이터베이스 관련
import chromadb
from chromadb.config import Settings


class PDFSplitter:
    """PDF를 페이지별로 분할하는 클래스"""
    
    @staticmethod
    def split_pdf(input_pdf: str, output_dir: str = None) -> int:
        """
        PDF를 페이지별로 분할
        
        Args:
            input_pdf: 입력 PDF 경로
            output_dir: 출력 디렉토리 (기본값: 입력파일명_split)
        
        Returns:
            분할된 페이지 수
        """
        if not output_dir:
            base_name = os.path.splitext(os.path.basename(input_pdf))[0]
            output_dir = os.path.join(os.path.dirname(input_pdf), f"{base_name}_split")
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(input_pdf, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            print(f"총 페이지 수: {num_pages}")
            
            # 각 페이지 분할
            for i in range(num_pages):
                pdf_writer = PyPDF2.PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[i])
                
                base_name = os.path.splitext(os.path.basename(input_pdf))[0]
                output_file = os.path.join(output_dir, f"{base_name}_page{i+1:02d}.pdf")
                
                with open(output_file, 'wb') as output:
                    pdf_writer.write(output)
                print(f"생성됨: {output_file}")
        
        return num_pages


class ExamTextExtractor:
    """시험 문제 텍스트 추출 및 파싱 클래스"""
    
    def __init__(self):
        self.question_patterns = [
            r'^(\d{1,2})\.\s*(.+)',  # 1. 문제
            r'^(\d{1,2})\s+(.+)',    # 1 문제 (점 없이)
        ]
        self.choice_patterns = [
            r'①', r'②', r'③', r'④', r'⑤',  # ○형 숫자
            r'\(1\)', r'\(2\)', r'\(3\)', r'\(4\)', r'\(5\)'  # (1) 형태
        ]
        self.passage_markers = r'\[(\d+)\s*[~∼]\s*(\d+)\]'  # [지문번호]
        
    def extract_text_from_page(self, pdf_path: str) -> str:
        """PDF 페이지에서 텍스트 추출"""
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            return page.extract_text() or ""
    
    def extract_all_text(self, pdf_dir: str) -> Dict[int, str]:
        """모든 PDF 페이지에서 텍스트 추출"""
        all_text = {}
        pdf_files = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
        
        for pdf_file in pdf_files:
            match = re.search(r'page(\d+)', pdf_file)
            if match:
                page_num = int(match.group(1))
                all_text[page_num] = self.extract_text_from_page(pdf_file)
        
        return all_text
    
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
        full_text = '\n'.join(lines[1:])
        
        # ○형 숫자 찾기
        for i, marker in enumerate(['①', '②', '③', '④', '⑤']):
            pattern = f'{marker}\s*(.+?)(?=[①②③④⑤]|$)'
            match = re.search(pattern, full_text, re.DOTALL)
            if match:
                option_text = match.group(1).strip()
                option_text = ' '.join(option_text.split())
                options.append({
                    "number": i + 1,
                    "text": option_text
                })
        
        return {
            "number": question_num,
            "question": question_text,
            "options": options
        }
    
    def extract_passage(self, text: str) -> Optional[str]:
        """지문 추출"""
        marker_match = re.search(self.passage_markers, text)
        if not marker_match:
            return None
        
        marker_pos = marker_match.end()
        passage_text = text[marker_pos:].strip()
        
        # 다음 문제 번호가 나오는 부분까지만 추출
        next_question_match = re.search(r'\n\d{1,2}[\.\s]', passage_text)
        if next_question_match:
            passage_text = passage_text[:next_question_match.start()]
        
        return passage_text.strip()


class ExamJSONGenerator:
    """시험 문제 JSON 생성 클래스"""
    
    def __init__(self):
        self.extractor = ExamTextExtractor()
        self.passages = {}  # 지문 저장용
        self.questions = {}  # 문제 저장용
        
    def determine_question_type(self, question_num: int) -> str:
        """문제 번호로 유형 판단"""
        if 1 <= question_num <= 9:
            return "독서"
        elif 10 <= question_num <= 34:
            return "문학"
        elif 35 <= question_num <= 45:
            return "화법과 작문"
        else:
            return "기타"
    
    def determine_subject_code(self, question_type: str) -> str:
        """문제 유형으로 과목 코드 판단"""
        type_to_code = {
            "화법": "01",
            "작문": "02",
            "독서": "03",
            "문학": "04",
            "언어": "05",
            "매체": "06",
            "화법과 작문": "12",
            "언어와 매체": "56"
        }
        return type_to_code.get(question_type, "03")  # 기본값: 독서
    
    def process_exam(self, pdf_dir: str, exam_info: Dict) -> List[Dict]:
        """시험 전체 처리"""
        all_text = self.extractor.extract_all_text(pdf_dir)
        
        # 지문과 문제 찾기
        self.find_passages_and_questions(all_text)
        
        # JSON 데이터 생성
        json_data_list = []
        for q_num, q_data in sorted(self.questions.items()):
            passage = self.passages.get(q_num, "")
            question_type = self.determine_question_type(q_num)
            subject_code = self.determine_subject_code(question_type)
            
            json_data = {
                "id": f"{exam_info['id_prefix']}_{q_num:02d}",
                "source": exam_info['source'],
                "year": exam_info['year'],
                "month": exam_info['month'],
                "exam_type_code": exam_info['exam_type_code'],
                "subject_code": subject_code,
                "type": question_type,
                "passage": passage,
                "context_box": "",
                "question": q_data["question"],
                "options": q_data["options"],
                "answer_rate": 0,
                "difficulty": ""
            }
            json_data_list.append(json_data)
        
        return json_data_list
    
    def find_passages_and_questions(self, all_text: Dict[int, str]):
        """지문과 문제 찾기"""
        passage_pattern = r'\[(\d+)\s*[~∼]\s*(\d+)\]'
        
        # 모든 페이지 통합 처리
        combined_text = ""
        for page_num in sorted(all_text.keys()):
            combined_text += f"\n===PAGE{page_num}===\n" + all_text[page_num]
        
        # 지문과 문제 추출 로직
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
                
                # 문제 및 선택지 수집
                question_data = self.collect_question_and_options(lines, i)
                if question_data:
                    self.questions[q_num] = question_data
                    i = question_data.get('end_index', i)
            
            # 지문 텍스트 추가
            elif current_passage_nums:
                current_passage_text += line + "\n"
            
            i += 1
        
        # 마지막 지문 저장
        if current_passage_nums:
            for num in current_passage_nums:
                self.passages[num] = current_passage_text.strip()
    
    def collect_question_and_options(self, lines: List[str], start_idx: int) -> Optional[Dict]:
        """문제와 선택지 수집"""
        match = re.match(r'^(\d{1,2})\s*\.\s*(.+)', lines[start_idx])
        if not match:
            return None
        
        q_text = match.group(2)
        options = []
        i = start_idx + 1
        
        # 선택지 찾기
        while i < len(lines) and len(options) < 5:
            line = lines[i]
            
            # 다음 문제가 나오면 중단
            if re.match(r'^(\d{1,2})\s*\.', line):
                break
            
            # 선택지 추출
            for idx, marker in enumerate(['①', '②', '③', '④', '⑤']):
                if marker in line:
                    option_text = self.extract_option_text(lines, i, marker)
                    if option_text:
                        options.append({
                            "number": idx + 1,
                            "text": option_text
                        })
            
            i += 1
        
        return {
            "question": q_text,
            "options": options,
            "end_index": i
        }
    
    def extract_option_text(self, lines: List[str], start_idx: int, marker: str) -> str:
        """선택지 텍스트 추출"""
        line = lines[start_idx]
        marker_pos = line.find(marker)
        if marker_pos == -1:
            return ""
        
        # 현재 마커부터 다음 마커까지 추출
        text = line[marker_pos + len(marker):].strip()
        
        # 다음 마커 찾기
        next_markers = ['①', '②', '③', '④', '⑤']
        for next_marker in next_markers:
            if next_marker != marker and next_marker in text:
                text = text[:text.find(next_marker)]
                break
        
        return text.strip()
    
    def save_json_files(self, json_data_list: List[Dict], output_dir: str):
        """JSON 파일 저장"""
        os.makedirs(output_dir, exist_ok=True)
        
        for data in json_data_list:
            filename = f"{data['id']}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"생성됨: {filepath}")


class SNDatabase:
    """수능 데이터베이스 클래스"""
    
    def __init__(self, db_path: str = "./sn_csat.db"):
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(name="sn_questions")
    
    def build_database(self, json_dir: str = "./db"):
        """JSON 파일들로 데이터베이스 구축"""
        json_files = glob.glob(os.path.join(json_dir, "*.json"))
        
        documents = []
        metadatas = []
        ids = []
        
        for json_file in sorted(json_files):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 문서 생성
                doc = f"지문: {data.get('passage', '')}\n"
                doc += f"문제: {data.get('question', '')}\n"
                doc += f"보기: {data.get('context_box', '')}"
                
                documents.append(doc)
                metadatas.append({
                    "id": data["id"],
                    "year": data["year"],
                    "month": data["month"],
                    "type": data.get("type", ""),
                    "source": data.get("source", "")
                })
                ids.append(data["id"])
        
        # 데이터베이스에 추가
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"데이터베이스 구축 완료: {len(documents)}개 문제")
    
    def search(self, query: str, n_results: int = 5):
        """데이터베이스 검색"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return results
    
    def get_by_id(self, question_id: str):
        """ID로 문제 가져오기"""
        result = self.collection.get(
            ids=[question_id]
        )
        
        if result['ids']:
            json_path = f"./db/{question_id}.json"
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        return None


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='수능 국어 PDF 처리 통합 도구')
    parser.add_argument('command', choices=['split', 'extract', 'build-db', 'search'],
                        help='실행할 명령')
    parser.add_argument('--input', '-i', help='입력 파일/디렉토리')
    parser.add_argument('--output', '-o', help='출력 디렉토리')
    parser.add_argument('--exam-year', type=int, help='시험 연도')
    parser.add_argument('--exam-month', type=int, help='시험 월')
    parser.add_argument('--query', '-q', help='검색 쿼리')
    
    args = parser.parse_args()
    
    if args.command == 'split':
        # PDF 분할
        if not args.input:
            print("입력 PDF 파일을 지정해주세요.")
            return
        
        splitter = PDFSplitter()
        splitter.split_pdf(args.input, args.output)
        
    elif args.command == 'extract':
        # JSON 추출
        if not args.input:
            print("PDF 디렉토리를 지정해주세요.")
            return
        
        # 시험 정보 설정
        exam_info = {
            'id_prefix': f"{args.exam_year % 100:02d}_{args.exam_month:02d}",
            'source': f"{args.exam_year}학년도 대학수학능력시험",
            'year': args.exam_year - 1 if args.exam_month == 11 else args.exam_year,
            'month': args.exam_month,
            'exam_type_code': 1 if args.exam_month == 11 else 2
        }
        
        generator = ExamJSONGenerator()
        json_data_list = generator.process_exam(args.input, exam_info)
        
        output_dir = args.output or './db'
        generator.save_json_files(json_data_list, output_dir)
        
    elif args.command == 'build-db':
        # 데이터베이스 구축
        db = SNDatabase()
        db.build_database(args.input or './db')
        
    elif args.command == 'search':
        # 검색
        if not args.query:
            print("검색어를 입력해주세요.")
            return
        
        db = SNDatabase()
        results = db.search(args.query)
        
        print(f"\n검색 결과 (쿼리: {args.query})")
        print("-" * 50)
        
        for i, (doc_id, metadata) in enumerate(zip(results['ids'][0], results['metadatas'][0])):
            print(f"\n{i+1}. {doc_id}")
            print(f"   출처: {metadata.get('source', '')}")
            print(f"   유형: {metadata.get('type', '')}")
            
            # 전체 문제 정보 가져오기
            full_data = db.get_by_id(doc_id)
            if full_data:
                print(f"   문제: {full_data.get('question', '')[:50]}...")


if __name__ == "__main__":
    main()