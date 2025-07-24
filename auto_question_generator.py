#!/usr/bin/env python3

import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
import os
from typing import List, Dict
import requests
import time
from anthropic import Anthropic

class AutoQuestionGenerator:
    def __init__(self, embeddings_path):
        """자동 문제 생성기 초기화"""
        print("벡터 DB 로딩 중...")
        with open(embeddings_path, 'rb') as f:
            data = pickle.load(f)
        
        self.documents = data['documents']
        self.embeddings = np.array(data['embeddings'])
        self.model_name = data['model_name']
        
        # 임베딩 모델 로드
        print(f"임베딩 모델 로드 중: {self.model_name}")
        self.model = SentenceTransformer(self.model_name, device='cpu')
        
        print("문제 생성기 준비 완료!")
        print(f"벡터 DB 위치: {embeddings_path}")
        print(f"총 {len(self.documents)}개의 문제가 DB에 저장되어 있습니다.")
    
    def find_similar_questions(self, passage: str, top_k: int = 5, min_similarity: float = 0.3) -> List[Dict]:
        """주어진 지문과 유사한 문제들을 벡터 DB에서 찾기"""
        print("지문과 유사한 문제들을 검색 중...")
        
        # 지문 임베딩
        passage_embedding = self.model.encode([passage])
        
        # 코사인 유사도 계산
        similarities = cosine_similarity(passage_embedding, self.embeddings)[0]
        
        # 최소 유사도 이상인 것들만 필터링
        valid_indices = np.where(similarities >= min_similarity)[0]
        valid_similarities = similarities[valid_indices]
        
        # 상위 k개 결과 추출
        if len(valid_indices) == 0:
            print("유사한 문제를 찾을 수 없습니다.")
            return []
        
        top_indices_in_valid = np.argsort(valid_similarities)[::-1][:top_k]
        top_indices = valid_indices[top_indices_in_valid]
        
        similar_questions = []
        for idx in top_indices:
            similar_questions.append({
                'filename': self.documents[idx]['filename'],
                'similarity': float(similarities[idx]),
                'data': self.documents[idx]['data']
            })
        
        print(f"{len(similar_questions)}개의 유사한 문제를 찾았습니다.")
        return similar_questions
    
    def generate_questions_with_claude(self, passage: str, similar_questions: List[Dict], question_count: int = 3) -> str:
        """Claude API를 사용하여 실제 문제 생성"""
        
        # 유사 문제들의 예시 구성
        examples = ""
        for i, item in enumerate(similar_questions[:3], 1):
            data = item['data']
            examples += f"\n=== 예시 {i} (유사도: {item['similarity']:.3f}) ===\n"
            examples += f"문제: {data.get('question', '')}\n"
            
            if data.get('options'):
                examples += "선택지:\n"
                for option in data['options']:
                    examples += f"{option.get('number', '')}. {option.get('text', '')}\n"
            examples += "\n"
        
        prompt = f"""다음 지문을 바탕으로 수능 국어 문제를 {question_count}개 만들어주세요.

=== 주어진 지문 ===
{passage}

=== 참고할 유사 문제 예시들 ===
{examples}

=== 문제 생성 조건 ===
1. 위의 예시들과 유사한 문제 유형과 형식으로 만들어주세요
2. 각 문제마다 5개의 선택지를 제공해주세요
3. 지문의 내용을 정확히 이해했는지 묻는 문제로 만들어주세요
4. 수능 국어 문제의 형식을 정확히 따라주세요
5. 정답과 해설도 함께 제공해주세요
6. 한국어로 출력해주세요

=== 출력 형식 ===
문제 1:
[문제 내용]

1. [선택지 1]
2. [선택지 2] 
3. [선택지 3]
4. [선택지 4]
5. [선택지 5]

정답: [정답 번호]
해설: [해설 내용]

---

문제 2:
...

JSON도 함께 출력해주세요:
```json
[
  {{
    "id": 1,
    "question": "문제 내용",
    "options": [
      {{"number": 1, "text": "선택지 1"}},
      {{"number": 2, "text": "선택지 2"}},
      {{"number": 3, "text": "선택지 3"}},
      {{"number": 4, "text": "선택지 4"}},
      {{"number": 5, "text": "선택지 5"}}
    ],
    "answer": 정답번호,
    "explanation": "해설 내용"
  }}
]
```"""

        try:
            print("Claude API를 통해 문제 생성 중...")
            
            # API 키 확인
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                return """
Claude API 키가 설정되지 않았습니다. 

다음 중 하나의 방법으로 API 키를 설정해주세요:
1. 환경 변수로 설정: export ANTHROPIC_API_KEY="your-api-key"
2. .env 파일에 설정: ANTHROPIC_API_KEY=your-api-key

API 키는 https://console.anthropic.com/에서 발급받을 수 있습니다.
"""
            
            # Claude API 클라이언트 초기화
            client = Anthropic(api_key=api_key)
            
            # Claude API 호출
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return response.content[0].text
                
        except Exception as e:
            return f"Claude API 호출 중 오류 발생: {str(e)}"
    
    def generate_questions_with_ollama(self, passage: str, similar_questions: List[Dict], question_count: int = 3) -> str:
        """Ollama API를 사용하여 실제 문제 생성"""
        
        # 유사 문제들의 예시 구성
        examples = ""
        for i, item in enumerate(similar_questions[:3], 1):
            data = item['data']
            examples += f"\n=== 예시 {i} (유사도: {item['similarity']:.3f}) ===\n"
            examples += f"문제: {data.get('question', '')}\n"
            
            if data.get('options'):
                examples += "선택지:\n"
                for option in data['options']:
                    examples += f"{option.get('number', '')}. {option.get('text', '')}\n"
            examples += "\n"
        
        prompt = f"""다음 지문을 바탕으로 수능 국어 문제를 {question_count}개 만들어주세요.

=== 주어진 지문 ===
{passage}

=== 참고할 유사 문제 예시들 ===
{examples}

=== 문제 생성 조건 ===
1. 위의 예시들과 유사한 문제 유형과 형식으로 만들어주세요
2. 각 문제마다 5개의 선택지를 제공해주세요
3. 지문의 내용을 정확히 이해했는지 묻는 문제로 만들어주세요
4. 수능 국어 문제의 형식을 정확히 따라주세요
5. 정답과 해설도 함께 제공해주세요
6. 한국어로 출력해주세요"""

        try:
            print("Ollama API를 통해 문제 생성 중...")
            
            # Ollama API 호출
            response = requests.post('http://localhost:11434/api/generate', 
                json={
                    'model': 'llama3.2:3b',  # 또는 사용 가능한 다른 모델
                    'prompt': prompt,
                    'stream': False
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                return f"API 호출 실패: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return "Ollama 서버에 연결할 수 없습니다. 'ollama serve' 명령으로 서버를 시작해주세요."
        except Exception as e:
            return f"문제 생성 중 오류 발생: {str(e)}"
    
    def generate_questions_with_transformers(self, passage: str, similar_questions: List[Dict], question_count: int = 3) -> str:
        """로컬 Transformers 모델을 사용하여 문제 생성 (간단한 버전)"""
        
        print("로컬 모델로 문제 패턴 분석 중...")
        
        # 간단한 템플릿 기반 문제 생성
        result = f"""
=== 생성된 문제 (템플릿 기반) ===

지문: {passage[:100]}...

참고된 유사 문제들:
"""
        
        for i, item in enumerate(similar_questions[:3], 1):
            data = item['data']
            result += f"{i}. {data.get('id', 'Unknown')} (유사도: {item['similarity']:.3f})\n"
            result += f"   문제 유형: {data.get('type', 'N/A')}\n"
            result += f"   문제: {data.get('question', '')[:80]}...\n\n"
        
        result += """
=== 추천 문제 생성 방식 ===
1. 지문의 핵심 내용을 파악하여 이해 문제 생성
2. 유사 문제들의 패턴을 따라 선택지 구성
3. '가장 적절한 것', '적절하지 않은 것' 형태의 문제 생성

=== AI 프롬프트 ===
더 정확한 문제 생성을 위해서는 ChatGPT나 Claude에 다음 프롬프트를 사용하세요:
(ai_prompt.txt 파일에 저장된 프롬프트 사용)
"""
        
        return result
    
    def process_passage_auto(self, passage: str, top_k: int = 5, question_count: int = 3, use_api: str = "local"):
        """지문을 처리하여 자동으로 문제 생성"""
        print(f"\n=== 자동 문제 생성 시작 ===")
        print(f"지문 길이: {len(passage)}자")
        print(f"생성 방식: {use_api}")
        
        # 1. 유사한 문제들 검색
        similar_questions = self.find_similar_questions(passage, top_k)
        
        if not similar_questions:
            print("유사한 문제를 찾을 수 없어 문제 생성을 중단합니다.")
            return
        
        # 2. 유사 문제들 출력
        print(f"\n=== 참고할 유사 문제들 ===")
        for i, item in enumerate(similar_questions, 1):
            data = item['data']
            print(f"{i}. {data.get('id', 'Unknown')} (유사도: {item['similarity']:.4f})")
            print(f"   문제: {data.get('question', '')[:80]}...")
            print(f"   유형: {data.get('type', 'N/A')}")
        
        # 3. 문제 생성
        if use_api == "claude":
            generated_questions = self.generate_questions_with_claude(passage, similar_questions, question_count)
        elif use_api == "ollama":
            generated_questions = self.generate_questions_with_ollama(passage, similar_questions, question_count)
        else:
            generated_questions = self.generate_questions_with_transformers(passage, similar_questions, question_count)
        
        # 4. 결과 출력 및 저장
        print(f"\n=== 생성된 문제 ===")
        print(generated_questions)
        
        # 결과를 파일로 저장
        output_file = "/Users/stillclie_mac/Documents/ug/snoriginal/generated_questions.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"=== 입력 지문 ===\n{passage}\n\n")
            f.write(f"=== 생성된 문제 ===\n{generated_questions}")
        
        print(f"\n결과가 '{output_file}' 파일로 저장되었습니다.")

def main():
    # 벡터 DB 경로
    embeddings_path = "/Users/stillclie_mac/Documents/ug/snoriginal/embeddings.pkl"
    
    # 파일 존재 확인
    if not os.path.exists(embeddings_path):
        print(f"벡터 DB 파일이 없습니다: {embeddings_path}")
        print("먼저 embed_json.py를 실행하여 벡터 DB를 생성해주세요.")
        return
    
    # 자동 문제 생성기 초기화
    generator = AutoQuestionGenerator(embeddings_path)
    
    print("\n=== 자동 문제 생성 시스템 ===")
    print("새로운 지문을 입력하면 실제 문제를 자동으로 생성합니다.")
    
    while True:
        print("\n옵션:")
        print("1. 지문 입력하여 자동 문제 생성")
        print("2. 파일에서 지문 읽어서 자동 문제 생성") 
        print("3. 예시 지문으로 테스트")
        print("4. 종료")
        
        choice = input("\n선택하세요 (1-4): ").strip()
        
        if choice == '1':
            print("\n지문을 입력하세요 (종료하려면 빈 줄 두 번):")
            lines = []
            empty_count = 0
            while True:
                line = input()
                if not line:
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                lines.append(line)
            
            passage = "\n".join(lines).strip()
            if passage:
                print("\n생성 방식을 선택하세요:")
                print("1. Claude API 사용 (추천, 가장 정확)")
                print("2. Ollama API 사용 (로컬, 서버 필요)")
                print("3. 로컬 템플릿 기반 (간단한 분석)")
                
                api_choice = input("선택 (1-3): ").strip()
                if api_choice == "1":
                    use_api = "claude"
                elif api_choice == "2":
                    use_api = "ollama"
                else:
                    use_api = "local"
                
                generator.process_passage_auto(passage, use_api=use_api)
        
        elif choice == '2':
            file_path = input("지문 파일 경로를 입력하세요: ").strip()
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    passage = f.read().strip()
                if passage:
                    print("\n생성 방식을 선택하세요:")
                    print("1. Claude API 사용 (추천)")
                    print("2. Ollama API 사용")
                    print("3. 로컬 템플릿 기반")
                    
                    api_choice = input("선택 (1-3): ").strip()
                    if api_choice == "1":
                        use_api = "claude"
                    elif api_choice == "2":
                        use_api = "ollama"
                    else:
                        use_api = "local"
                    
                    generator.process_passage_auto(passage, use_api=use_api)
            except Exception as e:
                print(f"파일 읽기 오류: {e}")
        
        elif choice == '3':
            # AI 관련 예시 지문
            sample_passage = """
현대 사회에서 인공지능 기술의 발달은 우리 삶의 다양한 영역에 큰 변화를 가져오고 있다. 
특히 자연어 처리 기술의 발전으로 인해 기계가 인간의 언어를 이해하고 생성하는 능력이 
크게 향상되었다. 이러한 변화는 교육 분야에도 적용되어, AI가 학생 개개인의 학습 수준을 
파악하고 맞춤형 학습 콘텐츠를 제공하는 것이 가능해졌다.

그러나 AI 기술의 도입에는 여러 우려사항도 존재한다. 무엇보다 AI가 인간의 창의성을 
대체할 수 있는가에 대한 근본적인 질문이 제기된다. 또한 AI에 대한 과도한 의존이 
인간의 사고력 저하를 초래할 수 있다는 우려도 있다.
"""
            print("예시 지문으로 자동 문제 생성합니다:")
            print(sample_passage.strip())
            
            print("\n생성 방식을 선택하세요:")
            print("1. Claude API 사용 (추천)")
            print("2. Ollama API 사용")
            print("3. 로컬 템플릿 기반")
            
            api_choice = input("선택 (1-3): ").strip()
            if api_choice == "1":
                use_api = "claude"
            elif api_choice == "2":
                use_api = "ollama"
            else:
                use_api = "local"
            
            generator.process_passage_auto(sample_passage.strip(), use_api=use_api)
        
        elif choice == '4':
            print("자동 문제 생성 시스템을 종료합니다.")
            break
        
        else:
            print("잘못된 선택입니다.")

if __name__ == "__main__":
    main()