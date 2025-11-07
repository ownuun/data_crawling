import os
from dotenv import load_dotenv
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import re
from notion_client import Client
from webdriver_manager.chrome import ChromeDriverManager  

# .env 파일 자동 로드 (존재할 경우만)
load_dotenv()

class WishketToNotion:
    def __init__(self, notion_token, database_id, start_id=1, end_id=100):
        self.start_id = start_id
        self.end_id = end_id
        self.crawl_delay = 5
        self.results = []
        
        # Notion 클라이언트
        self.notion = Client(auth=notion_token)
        self.database_id = database_id
        
        # Selenium 설정
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.set_page_load_timeout(30)
    
    def safe_extract(self, selector, default=None):
        """안전한 텍스트 추출"""
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element.text.strip()
        except:
            return default
    
    def extract_number(self, text):
        """숫자 추출"""
        if not text:
            return None
        text = text.replace(',', '').replace('원', '').replace('일', '').replace('명', '')
        match = re.search(r'\d+', text)
        return int(match.group()) if match else None
    
    def parse_date(self, date_str):
        """날짜 파싱"""
        if not date_str:
            return None
        try:
            match = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', date_str)
            if match:
                year, month, day = match.groups()
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except:
            pass
        return None
    
    def get_budget_range(self, amount):
        """예산 구간"""
        if not amount:
            return "알수없음"
        if amount < 5000000:
            return "500만이하"
        elif amount < 10000000:
            return "500-1000만"
        elif amount < 20000000:
            return "1000-2000만"
        elif amount < 50000000:
            return "2000-5000만"
        else:
            return "5000만이상"
    
    def get_competition(self, count):
        """경쟁률"""
        if count < 8:
            return "낮음"
        elif count < 15:
            return "중간"
        else:
            return "높음"
    
    def get_condition_value(self, row, label):
        """조건 값 추출 - condition-data 요소 직접 찾기"""
        try:
            # 여러 선택자로 시도
            selectors = [
                'p.condition-data',
                '.condition-data',
                'p.body-2.text900',
                '.project-detail-condition-row > p'
            ]

            for selector in selectors:
                try:
                    elem = row.find_element(By.CSS_SELECTOR, selector)
                    value = elem.text.strip()
                    if value and value != label:
                        return value
                except:
                    continue

            # 모든 선택자 실패시 row 전체 텍스트에서 label 제거
            full_text = row.text.strip()
            if label in full_text:
                value = full_text.replace(label, '', 1).strip()
                if value:
                    return value

            return None
        except:
            return None

    def extract_conditions(self):
        """상세 조건 추출"""
        conditions = {}
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, '.project-detail-condition-row')
            print(f"  🔍 찾은 조건 row 개수: {len(rows)}")
            for row in rows:
                try:
                    label_elem = row.find_element(By.CSS_SELECTOR, '.condition-label')
                    if not label_elem:
                        continue
                    label = label_elem.text.strip()

                    # row 전체 텍스트 확인
                    row_text = row.text.strip()
                    print(f"    📌 라벨: {label}")
                    print(f"       전체 텍스트: {row_text[:100]}")

                    if '모집 마감일' in label:
                        try:
                            value = self.get_condition_value(row, label)
                            if value:
                                conditions['deadline'] = value
                                print(f"      ✅ deadline: {value[:30]}")
                            else:
                                print(f"      ⚠️ deadline: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ deadline 실패: {e}")
                    elif '예상 시작일' in label:
                        try:
                            value = self.get_condition_value(row, label)
                            if value:
                                conditions['start_date'] = value
                                print(f"      ✅ start_date: {value[:30]}")
                            else:
                                print(f"      ⚠️ start_date: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ start_date 실패: {e}")
                    elif '진행 분류' in label:
                        try:
                            value = self.get_condition_value(row, label)
                            if value:
                                conditions['project_type'] = value
                                print(f"      ✅ project_type: {value[:30]}")
                            else:
                                print(f"      ⚠️ project_type: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ project_type 실패: {e}")
                    elif '기획 상태' in label:
                        try:
                            value = self.get_condition_value(row, label)
                            if value:
                                conditions['planning_status'] = value
                                print(f"      ✅ planning_status: {value[:30]}")
                            else:
                                print(f"      ⚠️ planning_status: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ planning_status 실패: {e}")
                    elif '프로젝트 경험' in label:
                        try:
                            value = self.get_condition_value(row, label)
                            if value:
                                conditions['project_experience'] = value
                                print(f"      ✅ project_experience: {value[:30]}")
                            else:
                                print(f"      ⚠️ project_experience: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ project_experience 실패: {e}")
                    elif '협업 예정 인력' in label or '협업인력' in label:
                        try:
                            value = self.get_condition_value(row, label)
                            if value:
                                conditions['collaboration_staff'] = value
                                print(f"      ✅ collaboration_staff: {value[:30]}")
                            else:
                                print(f"      ⚠️ collaboration_staff: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ collaboration_staff 실패: {e}")
                    elif '우선 순위' in label or '우선순위' in label:
                        try:
                            value = self.get_condition_value(row, label)
                            if value:
                                # "[1순위] 산출물 완성도 [2순위] 금액 [3순위] 일정 준수" 형태를 리스트로 분리
                                import re
                                priorities = re.findall(r'\[\d+순위\][^\[]+', value)
                                priorities = [p.strip() for p in priorities if p.strip()]

                                if priorities:
                                    conditions['priority'] = priorities
                                    print(f"      ✅ priority: {priorities}")
                                else:
                                    # 분리 실패시 전체를 하나로
                                    conditions['priority'] = [value]
                                    print(f"      ✅ priority (단일): {value[:30]}")
                            else:
                                print(f"      ⚠️ priority: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ priority 실패: {e}")
                    elif '관련 기술' in label:
                        try:
                            # subcategory-box 요소들로 개별 추출
                            tech_elements = row.find_elements(By.CSS_SELECTOR, '.subcategory-box')
                            techs = [elem.text.strip() for elem in tech_elements if elem.text.strip()]

                            if not techs:
                                # 실패시 전체 텍스트에서 추출
                                value = self.get_condition_value(row, label)
                                if value:
                                    techs = [t.strip() for t in value.split() if t.strip()]

                            if techs:
                                conditions['related_tech'] = techs
                                print(f"      ✅ related_tech: {techs}")
                            else:
                                print(f"      ⚠️ related_tech: 값을 찾을 수 없음")
                        except Exception as e:
                            print(f"      ❌ related_tech 실패: {e}")
                except Exception as e:
                    continue
        except Exception as e:
            print(f"  ⚠️ 조건 추출 중 오류: {str(e)}")
        return conditions
    
    def extract_tech_stack(self):
        """기술 스택/관련 기술 추출"""
        try:
            # 기술 스택은 여러 위치에 있을 수 있음
            tech_elements = self.driver.find_elements(By.CSS_SELECTOR, '.project-skill, .skill-badge, .tech-stack, .subcategory-box')
            techs = [elem.text.strip() for elem in tech_elements if elem.text.strip()]
            return ', '.join(techs) if techs else None
        except:
            return None

    def extract_contract_info(self):
        """기간제 계약 정보 추출"""
        contract_info = {}
        try:
            # project-target-info 영역이 있는지 확인
            target_info = self.driver.find_elements(By.CSS_SELECTOR, '.project-target-info')
            if not target_info:
                return contract_info

            # 역할 (풀스택 개발자 등)
            try:
                role = self.driver.find_element(By.CSS_SELECTOR, '.project-target-role').text.strip()
                contract_info['role'] = role
            except:
                pass

            # 레벨
            try:
                level_elem = self.driver.find_element(By.CSS_SELECTOR, '.project-target-detail-row-info.level')
                contract_info['level'] = level_elem.text.strip()
            except:
                pass

            # 경력
            try:
                exp_elem = self.driver.find_element(By.CSS_SELECTOR, '.project-target-detail-row-info.experience')
                contract_info['experience'] = exp_elem.text.strip()
            except:
                pass

            # 예상 금액 (월급)
            try:
                budget_elem = self.driver.find_element(By.CSS_SELECTOR, '.project-target-detail-row-info.budget')
                budget_text = budget_elem.text.strip()
                contract_info['monthly_budget_text'] = budget_text
                # 숫자 추출 (예: "3,000,000원/월" -> 3000000)
                contract_info['monthly_budget'] = self.extract_number(budget_text)
            except:
                pass

            # 근무 조건들 (근무 시작일, 예상 기간, 근무 위치)
            try:
                condition_rows = self.driver.find_elements(By.CSS_SELECTOR, '.target-condition-row')
                for row in condition_rows:
                    try:
                        title = row.find_element(By.CSS_SELECTOR, '.condition-row-title').text.strip()
                        data = row.find_element(By.CSS_SELECTOR, '.condition-row-data').text.strip()

                        if '근무 시작일' in title:
                            contract_info['work_start_date'] = data
                        elif '예상 기간' in title:
                            contract_info['work_duration_text'] = data
                            # 숫자 추출 (예: "90일" -> 90)
                            contract_info['work_duration'] = self.extract_number(data)
                        elif '근무 위치' in title:
                            contract_info['work_location'] = data
                    except:
                        continue
            except:
                pass

            # 필요 스킬
            try:
                skill_elements = self.driver.find_elements(By.CSS_SELECTOR, '.target-require-skills-box .skill-stack')
                skills = []
                for skill_elem in skill_elements:
                    skill_text = skill_elem.text.strip()
                    # "Java 경력 무관" 형태에서 기술명만 추출 (첫 번째 줄바꿈 전까지)
                    skill_name = skill_text.split('\n')[0].strip()
                    if skill_name:
                        skills.append(skill_name)
                contract_info['required_skills'] = skills
            except:
                pass

        except Exception as e:
            print(f"  ⚠️ 기간제 정보 추출 중 오류: {str(e)}")

        return contract_info
    
    def crawl_project(self, project_id):
        """프로젝트 크롤링"""
        url = f"https://www.wishket.com/project/{project_id}/"
        
        try:
            self.driver.get(url)
            time.sleep(1)  # 페이지 로딩 대기
            
            # 리다이렉트 체크
            current_url = self.driver.current_url
            if '/project/' in current_url and f'/project/{project_id}' not in current_url:
                print(f"⏭️  프로젝트 {project_id}: 존재하지 않음 (리다이렉트)")
                return None
            
            # 404 페이지 체크
            if "404" in self.driver.page_source or "찾을 수 없" in self.driver.page_source:
                print(f"⏭️  프로젝트 {project_id}: 404")
                return None
            
            # 프라이빗 프로젝트 체크
            if "float-private-box" in self.driver.page_source or "프라이빗 매칭 프로젝트" in self.driver.page_source:
                print(f"🔒 프로젝트 {project_id}: 프라이빗 프로젝트 (스킵)")
                return None
            
            # 프로젝트 페이지 확인
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "project-content-condition"))
                )
                # 조금 더 대기 (동적 콘텐츠 로딩)
                time.sleep(2)
            except:
                print(f"⏭️  프로젝트 {project_id}: 유효하지 않은 페이지")
                return None
            
            data = {
                'project_id': project_id,
                'url': url,
            }
            
            # === 기본 정보 ===
            data['title'] = self.safe_extract('h1') or f"프로젝트 {project_id}"

            # === 프로젝트 타입 (외주/기간제) ===
            project_type_mark = self.safe_extract('.status-mark.project-type-mark')
            data['project_type_mark'] = project_type_mark  # "외주" 또는 "기간제"

            # === 예산 ===
            budget_text = self.safe_extract('.project-budget .project-condition-data')
            data['budget'] = self.extract_number(budget_text)
            data['budget_range'] = self.get_budget_range(data['budget'])
            data['budget_negotiable'] = '조율' in str(self.safe_extract('.project-budget .condition-additional-info-text'))
            
            # === 기간 ===
            duration_text = self.safe_extract('.project-term .project-condition-data')
            data['duration'] = self.extract_number(duration_text)
            data['duration_negotiable'] = '조율' in str(self.safe_extract('.project-term .condition-additional-info-text'))
            
            # === 지원자 ===
            applicants_text = self.safe_extract('.project-applicant .project-condition-data')
            data['applicants'] = self.extract_number(applicants_text) or 0
            data['competition'] = self.get_competition(data['applicants'])
            
            # === 상세 조건들 ===
            conditions = self.extract_conditions()
            data.update(conditions)

            # 디버깅: 추출된 조건 출력
            if conditions:
                print(f"  📋 추출된 조건: {list(conditions.keys())}")

            # 날짜 파싱
            data['deadline_iso'] = self.parse_date(data.get('deadline'))
            data['start_date_iso'] = self.parse_date(data.get('start_date'))
            
            # === 카테고리 ===
            try:
                badges = self.driver.find_elements(By.CSS_SELECTOR, '.project-category, .badge')
                raw_categories = [b.text.strip() for b in badges if b.text.strip()]
                # 쉼표 제거
                categories = []
                for cat in raw_categories[:5]:
                    if ',' in cat:
                        sub_cats = [c.strip() for c in cat.split(',') if c.strip()]
                        categories.extend(sub_cats)
                    else:
                        categories.append(cat)
                data['categories'] = categories[:10]
            except:
                data['categories'] = []
            
            # === 플랫폼 ===
            data['platform'] = self.safe_extract('.project-platform')
            
            # === 기술 스택 ===
            data['tech_stack'] = self.extract_tech_stack()

            # === 기간제 계약 정보 ===
            contract_info = self.extract_contract_info()
            data.update(contract_info)

            # === 업무 내용 (description) ===
            description_elem = self.safe_extract('.project-description .project-description-box')
            data['description'] = description_elem
            
            # === 상태 ===
            page_source = self.driver.page_source
            data['status'] = '마감' if '마감' in page_source else '모집중'
            
            # === 수집일 ===
            data['collected'] = datetime.now().strftime('%Y-%m-%d')
            
            print(f"✅ {project_id}: {data['title'][:40]}")
            return data
            
        except Exception as e:
            print(f"❌ {project_id}: {str(e)}")
            return None
    def text_to_blocks(self, text, max_length=2000):
        """텍스트를 노션 블록으로 변환 (2000자 제한 고려)"""
        if not text:
            return []
        
        blocks = []
        # HTML br 태그를 줄바꿈으로 변환
        text = text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        
        # 2000자씩 나누기
        chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
        
        for chunk in chunks:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })
        
        return blocks
    
    def upload_to_notion(self, data):
        """노션 업로드"""
        try:
            # === Properties (데이터베이스 속성) ===
            properties = {
                "프로젝트명": {
                    "title": [{"text": {"content": data['title'][:100]}}]
                },
                "URL": {
                    "url": data['url']
                },
                "플랫폼": {
                    "url": "https://www.wishket.com/"
                },
                "상태": {
                    "select": {"name": data['status']}
                },
                "수집일": {
                    "date": {"start": data['collected']}
                },
                "지원여부": {
                    "checkbox": False
                }
            }

            # 프로젝트 타입 (외주/기간제)
            if data.get('project_type_mark'):
                properties["프로젝트타입"] = {
                    "select": {"name": data['project_type_mark']}
                }
            
            # 예산 (기간제 월예상금액이 있으면 우선 사용)
            budget_value = data.get('monthly_budget') or data.get('budget')
            if budget_value:
                properties["예산"] = {"number": budget_value}
                properties["예산구간"] = {"select": {"name": self.get_budget_range(budget_value)}}

            # 기간 (기간제 근무기간이 있으면 우선 사용)
            duration_value = data.get('work_duration') or data.get('duration')
            if duration_value:
                properties["기간(일)"] = {"number": duration_value}
            
            # 지원자
            properties["지원자수"] = {"number": data['applicants']}
            properties["경쟁률"] = {"select": {"name": data['competition']}}
            
            # 마감일
            if data.get('deadline_iso'):
                properties["마감일"] = {"date": {"start": data['deadline_iso']}}

            # 시작예정일 (Rich text)
            if data.get('start_date'):
                properties["시작예정일"] = {
                    "rich_text": [{"text": {"content": data['start_date'][:2000]}}]
                }
            
            # 카테고리 (Multi-select, 쉼표 제거)
            if data.get('categories'):
                clean_categories = [cat.replace(',', '').strip() for cat in data['categories'][:10] if cat.strip()]
                if clean_categories:
                    properties["카테고리"] = {
                        "multi_select": [{"name": cat[:100]} for cat in clean_categories]
                    }
            
            # 진행분류 (Multi-select)
            if data.get('project_type'):
                # 쉼표를 공백으로 대체
                clean_project_type = data['project_type'].replace(',', ' ')
                properties["진행분류"] = {
                    "multi_select": [{"name": clean_project_type[:100]}]
                }
            
            # 기획상태 (Multi-select)
            if data.get('planning_status'):
                # 쉼표를 공백으로 대체
                clean_planning_status = data['planning_status'].replace(',', ' ')
                properties["기획상태"] = {
                    "multi_select": [{"name": clean_planning_status[:100]}]
                }
            
            # 프로젝트경험 (Multi-select)
            if data.get('project_experience'):
                # 쉼표를 공백으로 대체
                clean_project_experience = data['project_experience'].replace(',', ' ')
                properties["프로젝트경험"] = {
                    "multi_select": [{"name": clean_project_experience[:100]}]
                }
            
            # 협업인력 (Multi-select)
            if data.get('collaboration_staff'):
                # 쉼표를 공백으로 대체
                clean_collaboration_staff = data['collaboration_staff'].replace(',', ' ')
                properties["협업인력"] = {
                    "multi_select": [{"name": clean_collaboration_staff[:100]}]
                }
            
            # 우선순위 (Multi-select - 리스트로 받음)
            if data.get('priority'):
                priorities = data['priority']
                # 리스트인 경우 그대로 사용, 문자열인 경우 리스트로 변환
                if isinstance(priorities, str):
                    priorities = [priorities]

                if priorities:
                    # 각 항목에서 쉼표를 공백으로 대체
                    clean_priorities = [p.replace(',', ' ').strip() for p in priorities[:5] if p.strip()]
                    properties["우선순위"] = {
                        "multi_select": [{"name": p[:100]} for p in clean_priorities]
                    }
            
            # 관련기술 (Multi-select - 쉼표로 분리)
            all_techs = []
            if data.get('tech_stack'):
                techs = [t.strip().replace(',', '') for t in data['tech_stack'].split(',') if t.strip()]
                all_techs.extend(techs)

            # related_tech도 추가 (조건 섹션에서 추출된 기술)
            if data.get('related_tech'):
                all_techs.extend(data['related_tech'])

            # 중복 제거
            all_techs = list(dict.fromkeys(all_techs))

            if all_techs:
                properties["관련기술"] = {
                    "multi_select": [{"name": tech[:100]} for tech in all_techs[:20]]
                }

            # === 기간제 계약 정보 ===
            # 역할 (직무)
            if data.get('role'):
                properties["역할"] = {
                    "rich_text": [{"text": {"content": data['role'][:2000]}}]
                }

            # 레벨
            if data.get(
                'level'):
                properties["레벨"] = {
                    "select": {"name": data['level'][:100]}
                }

            # 경력
            if data.get('experience'):
                properties["경력"] = {
                    "rich_text": [{"text": {"content": data['experience'][:2000]}}]
                }

            # 근무 위치
            if data.get('work_location'):
                properties["근무위치"] = {
                    "select": {"name": data['work_location'][:100]}
                }

            # 필요 스킬 (Multi-select)
            if data.get('required_skills'):
                # 각 스킬에서 쉼표를 공백으로 대체
                clean_skills = [skill.replace(',', ' ')[:100] for skill in data['required_skills'][:20]]
                properties["필요스킬"] = {
                    "multi_select": [{"name": skill} for skill in clean_skills]
                }

            # === 페이지 생성 ===
            page = self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            # === 업무 내용을 자식 페이지로 추가 ===
            if data.get('description'):
                child_page = self.notion.pages.create(
                    parent={"page_id": page['id']},
                    properties={
                        "title": {
                            "title": [{"text": {"content": "업무 내용"}}]
                        }
                    },
                    children=self.text_to_blocks(data['description'])
                )
            
            return True
            
        except Exception as e:
            print(f"  ⚠️ 노션 업로드 실패: {str(e)}")
            return False


    def run(self):
        """실행"""
        print("="*70)
        print("🚀 위시켓 → 노션 자동화 (Full Version)")
        print("="*70)
        print(f"📊 범위: {self.start_id} ~ {self.end_id}")
        print(f"⏱️ 예상: {(self.end_id - self.start_id + 1) * 5 / 60:.0f}분")
        print("="*70 + "\n")
        
        success = 0
        start_time = time.time()
        
        for pid in range(self.start_id, self.end_id + 1):
            # 크롤링
            data = self.crawl_project(pid)
            
            if data:
                # 노션 업로드
                if self.upload_to_notion(data):
                    success += 1
                    print(f"  ✅ 노션 저장 완료 (업무내용 포함)\n")
                
                # 백업
                self.results.append(data)
            
            # 진행률
            if pid % 10 == 0:
                progress = ((pid - self.start_id + 1) / (self.end_id - self.start_id + 1)) * 100
                print(f"📊 진행률: {progress:.0f}% | 성공: {success}개\n")
            
            # 백업 (50개마다)
            if len(self.results) % 50 == 0 and len(self.results) > 0:
                df = pd.DataFrame(self.results)
                filename = f"wishket_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                df.to_excel(filename, index=False)
                print(f"💾 중간 백업: {filename}\n")
            
            # 대기
            time.sleep(self.crawl_delay)
        
        # 완료
        self.driver.quit()
        
        # 최종 백업
        if self.results:
            df = pd.DataFrame(self.results)
            filename = f"wishket_final_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            df.to_excel(filename, index=False)
            print(f"\n💾 최종 백업: {filename}")
        
        elapsed = time.time() - start_time
        print("\n" + "="*70)
        print(f"✨ 완료! {success}개 업로드 | {elapsed/60:.1f}분 소요")
        print("="*70)


# ========================================
# 실행
# ========================================

if __name__ == "__main__":
    
    
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
    DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

    if not NOTION_TOKEN or not DATABASE_ID:
        raise RuntimeError(
            "환경변수 NOTION_TOKEN/NOTION_DATABASE_ID가 설정되어 있어야 합니다."
        )

    # 설정
    START_ID = 140006
    END_ID = 160000 
    
    print("\n🎯 위시켓 → 노션 자동화 (Full Version)")
    print(f"📊 크롤링: {START_ID} ~ {END_ID} ({END_ID-START_ID+1}개)")
    print(f"⏱️ 예상 시간: {(END_ID-START_ID+1)*5/60:.0f}분")
    print("\n📋 수집 정보:")
    print("  ✅ 기본: 제목, 예산, 기간, 지원자수, 마감일")
    print("  ✅ 추가: 기획상태, 프로젝트경험, 협업인력, 우선순위, 관련기술")
    print("  ✅ 업무내용: 자식 페이지로 생성\n")
    
    response = input("시작하시겠습니까? (y/n): ")
    
    if response.lower() == 'y':
        crawler = WishketToNotion(
            notion_token=NOTION_TOKEN,
            database_id=DATABASE_ID,
            start_id=START_ID,
            end_id=END_ID
        )
        
        try:
            crawler.run()
        except KeyboardInterrupt:
            print("\n\n⚠️ 중단됨")
            crawler.driver.quit()
    else:
        print("취소되었습니다.")
