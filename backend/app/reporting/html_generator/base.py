"""
HTML Generator Base Class

HTML 템플릿을 읽어서 JSON 데이터를 채워넣는 기본 클래스
"""
from pathlib import Path
from typing import Optional
import json


class BaseHTMLGenerator:
    """HTML 생성 기본 클래스"""
    
    # 프로젝트 루트 찾기 (backend/app/reporting/html_generator/base.py -> backend/)
    _BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    
    # 기본 템플릿 경로 (절대 경로)
    TEMPLATE_DIR = _BASE_DIR / "Data" / "reports" / "html"
    OUTPUT_DIR = _BASE_DIR / "output"
    
    def __init__(self, template_filename: str):
        """
        Args:
            template_filename: 템플릿 HTML 파일명 (예: "일일보고서.html")
        """
        self.template_path = self.TEMPLATE_DIR / template_filename
        
        # 출력 디렉토리 생성
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # 템플릿 파일 존재 확인
        if not self.template_path.exists():
            print(f"⚠️  템플릿 파일을 찾을 수 없습니다: {self.template_path}")
            print(f"   템플릿 디렉토리: {self.TEMPLATE_DIR}")
            print(f"   확인해주세요: backend/Data/reports/html/{template_filename}")
    
    def _load_template(self) -> str:
        """HTML 템플릿 파일 읽기"""
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _inject_data_and_auto_load(self, html_content: str, json_data: dict) -> str:
        """
        HTML에 JSON 데이터를 주입하고 자동으로 loadFromJSON 호출
        
        Args:
            html_content: 원본 HTML 내용
            json_data: 주입할 JSON 데이터
            
        Returns:
            데이터가 주입된 HTML 내용
        """
        # JSON 데이터를 JavaScript 변수로 변환
        json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
        
        # </script> 태그 앞에 데이터 주입 및 자동 로드 스크립트 추가
        injection_script = f"""
        // JSON 데이터 주입
        const reportData = {json_str};
        
        // 페이지 로드 시 자동으로 데이터 로드
        if (typeof loadFromJSON === 'function') {{
            loadFromJSON(reportData);
        }} else {{
            console.error('loadFromJSON function not found');
        }}
        """
        
        # </body> 태그 앞에 스크립트 삽입
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'<script>{injection_script}</script>\n</body>')
        else:
            # </body> 태그가 없으면 </html> 앞에 추가
            html_content = html_content.replace('</html>', f'<script>{injection_script}</script>\n</html>')
        
        return html_content
    
    def _save_html(self, html_content: str, output_filename: str, subdirectory: str = "") -> Path:
        """
        HTML 파일 저장
        
        Args:
            html_content: 저장할 HTML 내용
            output_filename: 출력 파일명
            subdirectory: 하위 디렉토리 (예: "daily", "weekly", "monthly")
            
        Returns:
            저장된 파일 경로
        """
        if subdirectory:
            output_dir = self.OUTPUT_DIR / subdirectory
        else:
            output_dir = self.OUTPUT_DIR
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path

