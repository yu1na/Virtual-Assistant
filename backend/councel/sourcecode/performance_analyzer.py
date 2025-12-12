"""
Performance Analysis Tool
생성날짜: 2025.12.03
설명: Python 파일의 모든 함수에 대해 실행 시간, 시간복잡도, 공간복잡도, 메모리 사용량, 병목 구간을 분석
"""

import os
import sys
import time
import re
import tracemalloc
import inspect
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional, Tuple
from datetime import datetime
import json
import numpy as np
from scipy import stats


class FunctionAnalyzer:
    """함수 분석 메인 클래스"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.module = None
        self.functions = {}
        self.classes = {}
        self.results = []
        
    def load_module(self) -> bool:
        """절대 경로에서 모듈 동적 로드"""
        try:
            if not self.file_path.exists():
                print(f"❌ 파일을 찾을 수 없습니다: {self.file_path}")
                return False
            
            # 모듈 이름 생성
            module_name = self.file_path.stem
            
            # 모듈 스펙 생성
            spec = importlib.util.spec_from_file_location(module_name, self.file_path)
            if spec is None or spec.loader is None:
                print(f"❌ 모듈 스펙을 생성할 수 없습니다: {self.file_path}")
                return False
            
            # 모듈 로드
            self.module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = self.module
            spec.loader.exec_module(self.module)
            
            print(f"✅ 모듈 로드 성공: {module_name}")
            return True
            
        except Exception as e:
            print(f"❌ 모듈 로드 실패: {e}")
            traceback.print_exc()
            return False
    
    def extract_functions(self):
        """모듈의 모든 함수와 클래스 메서드 추출"""
        if self.module is None:
            return
        
        # 일반 함수 추출
        for name, obj in inspect.getmembers(self.module, inspect.isfunction):
            if obj.__module__ == self.module.__name__:
                try:
                    source_code = inspect.getsource(obj)
                    source_lines = len(source_code.split('\n'))
                except:
                    source_code = ""
                    source_lines = 0
                
                self.functions[name] = {
                    'type': 'function',
                    'callable': obj,
                    'signature': str(inspect.signature(obj)),
                    'source_lines': source_lines,
                    'source_code': source_code
                }
        
        # 클래스 및 메서드 추출
        for class_name, class_obj in inspect.getmembers(self.module, inspect.isclass):
            if class_obj.__module__ == self.module.__name__:
                methods = {}
                for method_name, method_obj in inspect.getmembers(class_obj, inspect.isfunction):
                    if not method_name.startswith('_') or method_name == '__init__':
                        try:
                            source_code = inspect.getsource(method_obj)
                            source_lines = len(source_code.split('\n'))
                        except:
                            source_code = ""
                            source_lines = 0
                        
                        methods[method_name] = {
                            'type': 'method',
                            'callable': method_obj,
                            'signature': str(inspect.signature(method_obj)),
                            'source_lines': source_lines,
                            'source_code': source_code
                        }
                
                self.classes[class_name] = {
                    'class_obj': class_obj,
                    'methods': methods
                }
        
        total_functions = len(self.functions) + sum(len(c['methods']) for c in self.classes.values())
        print(f"✅ 함수 추출 완료: {len(self.functions)}개 함수, {len(self.classes)}개 클래스 ({total_functions}개 총 함수)")
    
    def generate_default_value(self, param: inspect.Parameter) -> Any:
        """파라미터 타입에 맞는 기본값 생성"""
        # 타입 힌트 확인
        param_type = param.annotation
        param_name = param.name.lower()
        
        # 타입 기반 기본값 생성
        if param_type != inspect.Parameter.empty:
            type_str = str(param_type)
            
            # 기본 타입들
            if 'str' in type_str or 'String' in type_str:
                if 'path' in param_name or 'file' in param_name or 'dir' in param_name:
                    return Path("test.txt")
                return "test_string"
            elif 'int' in type_str:
                return 0
            elif 'float' in type_str:
                return 0.0
            elif 'bool' in type_str:
                return False
            elif 'list' in type_str or 'List' in type_str:
                return []
            elif 'dict' in type_str or 'Dict' in type_str:
                return {}
            elif 'Path' in type_str or 'pathlib' in type_str:
                return Path("test.txt")
            elif 'tuple' in type_str or 'Tuple' in type_str:
                return ()
            elif 'set' in type_str or 'Set' in type_str:
                return set()
            elif 'Any' in type_str:
                return None
        
        # 타입 힌트가 없으면 파라미터 이름으로 추정
        if 'path' in param_name or 'file' in param_name or 'dir' in param_name:
            return Path("test.txt")
        elif 'text' in param_name or 'content' in param_name or 'str' in param_name or 'string' in param_name:
            return "test_string"
        elif 'num' in param_name or 'count' in param_name or 'size' in param_name or 'int' in param_name:
            return 0
        elif 'float' in param_name or 'ratio' in param_name:
            return 0.0
        elif 'bool' in param_name or 'flag' in param_name:
            return False
        elif 'list' in param_name or 'array' in param_name or 'items' in param_name:
            return []
        elif 'dict' in param_name or 'data' in param_name or 'metadata' in param_name or 'kwargs' in param_name:
            return {}
        elif 'tuple' in param_name:
            return ()
        elif 'set' in param_name:
            return set()
        else:
            # 기본값으로 None
            return None
    
    def prepare_function_args(self, func: Callable) -> Tuple[tuple, dict]:
        """함수 실행을 위한 인자 준비"""
        sig = inspect.signature(func)
        args = []
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            # 기본값이 있으면 스킵
            if param.default != inspect.Parameter.empty:
                continue
            
            # 더미 값 생성
            default_value = self.generate_default_value(param)
            
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                # *args
                continue
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                # **kwargs
                continue
            elif param.kind == inspect.Parameter.POSITIONAL_ONLY:
                args.append(default_value)
            else:
                kwargs[param_name] = default_value
        
        return tuple(args), kwargs
    
    def measure_execution_time(self, func: Callable, args: tuple = (), kwargs: dict = None, iterations: int = 100) -> Dict[str, float]:
        """실행 시간 측정"""
        if kwargs is None:
            kwargs = {}
        
        times = []
        
        try:
            # 워밍업
            for _ in range(min(10, iterations)):
                try:
                    func(*args, **kwargs)
                except:
                    pass
            
            # 실제 측정
            for _ in range(iterations):
                start = time.perf_counter()
                try:
                    func(*args, **kwargs)
                    end = time.perf_counter()
                    times.append((end - start) * 1000)  # ms 단위
                except Exception as e:
                    # 실행 불가능한 함수
                    return {
                        'avg_time_ms': None,
                        'min_time_ms': None,
                        'max_time_ms': None,
                        'std_time_ms': None,
                        'error': str(e)
                    }
            
            return {
                'avg_time_ms': np.mean(times),
                'min_time_ms': np.min(times),
                'max_time_ms': np.max(times),
                'std_time_ms': np.std(times),
                'error': None
            }
            
        except Exception as e:
            return {
                'avg_time_ms': None,
                'min_time_ms': None,
                'max_time_ms': None,
                'std_time_ms': None,
                'error': str(e)
            }
    
    def measure_memory_usage(self, func: Callable, args: tuple = (), kwargs: dict = None) -> Dict[str, float]:
        """메모리 사용량 측정"""
        if kwargs is None:
            kwargs = {}
        
        try:
            tracemalloc.start()
            
            try:
                func(*args, **kwargs)
            except:
                pass
            
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            return {
                'current_mb': current / (1024 * 1024),
                'peak_mb': peak / (1024 * 1024),
                'error': None
            }
            
        except Exception as e:
            tracemalloc.stop()
            return {
                'current_mb': None,
                'peak_mb': None,
                'error': str(e)
            }
    
    def estimate_time_complexity_static(self, source_code: str, source_lines: int) -> str:
        """정적 분석으로 시간복잡도 추정"""
        if not source_code:
            # 소스 코드가 없으면 소스 라인 수 기반으로 기본 추정
            if source_lines < 10:
                return "O(1)"
            elif source_lines < 30:
                return "O(n)"
            elif source_lines < 100:
                return "O(n log n)"
            else:
                return "O(n²)"
        
        try:
            # 소스 코드에서 루프 패턴 분석
            nested_loops = 0
            has_while = 'while' in source_code.lower()
            has_for = 'for' in source_code.lower()
            has_nested_for = source_code.count('for ') >= 2
            
            # 재귀 함수 체크
            has_recursion = False
            func_def_match = re.search(r'def\s+(\w+)', source_code)
            if func_def_match:
                func_name = func_def_match.group(1)
                func_body = source_code.split(':', 1)[1] if ':' in source_code else source_code
                has_recursion = func_name in func_body or f'self.{func_name}' in func_body
            
            # 중첩된 for 루프 개수 추정
            lines = source_code.split('\n')
            indent_levels = []
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith('for ') or stripped.startswith('while '):
                    indent = len(line) - len(stripped)
                    indent_levels.append(indent)
            
            # 중첩 레벨 계산
            if len(indent_levels) > 1:
                nested_loops = len(set(indent_levels))
            
            # 소스 코드 기반 추정
            if nested_loops >= 3:
                return "O(n³+)"
            elif nested_loops == 2:
                return "O(n²)"
            elif has_nested_for:
                return "O(n²)"
            elif has_recursion:
                if source_lines < 20:
                    return "O(log n)"
                else:
                    return "O(n)"
            elif has_for or has_while:
                if source_lines < 30:
                    return "O(n)"
                else:
                    return "O(n log n)"
            else:
                return "O(1)"
                
        except Exception as e:
            # 예외 발생 시 소스 라인 수 기반으로 기본 추정
            if source_lines < 10:
                return "O(1)"
            elif source_lines < 30:
                return "O(n)"
            elif source_lines < 100:
                return "O(n log n)"
            else:
                return "O(n²)"
    
    def estimate_time_complexity_dynamic(self, func: Callable, args: tuple, kwargs: dict) -> Optional[str]:
        """동적 분석으로 시간복잡도 추정 (회귀 분석)"""
        try:
            # 입력 크기를 변화시키며 실행 시간 측정
            sizes = [10, 50, 100, 500, 1000]
            times = []
            
            for size in sizes:
                # 크기에 따라 인자 조정 (리스트나 문자열 크기 증가)
                modified_args = []
                for arg in args:
                    if isinstance(arg, str):
                        modified_args.append("x" * size)
                    elif isinstance(arg, (list, tuple)):
                        modified_args.append(list(range(size)))
                    elif isinstance(arg, dict):
                        modified_args.append({i: i for i in range(size)})
                    else:
                        modified_args.append(arg)
                
                # 실행 시간 측정
                start = time.perf_counter()
                try:
                    func(*modified_args, **kwargs)
                    end = time.perf_counter()
                    times.append(end - start)
                except:
                    return None
            
            # 회귀 분석
            sizes_np = np.array(sizes)
            times_np = np.array(times)
            
            # O(1) 체크
            if np.std(times_np) < np.mean(times_np) * 0.1:
                return "O(1)"
            
            # O(log n) 체크
            log_sizes = np.log(sizes_np)
            _, _, r_value_log, _, _ = stats.linregress(log_sizes, times_np)
            
            # O(n) 체크
            _, _, r_value_linear, _, _ = stats.linregress(sizes_np, times_np)
            
            # O(n log n) 체크
            nlogn_sizes = sizes_np * np.log(sizes_np)
            _, _, r_value_nlogn, _, _ = stats.linregress(nlogn_sizes, times_np)
            
            # O(n²) 체크
            squared_sizes = sizes_np ** 2
            _, _, r_value_squared, _, _ = stats.linregress(squared_sizes, times_np)
            
            # 가장 높은 R² 값 선택
            r_values = {
                'O(log n)': r_value_log ** 2,
                'O(n)': r_value_linear ** 2,
                'O(n log n)': r_value_nlogn ** 2,
                'O(n²)': r_value_squared ** 2
            }
            
            best_fit = max(r_values, key=r_values.get)
            
            # R² 값이 0.8 이상이면 신뢰할 수 있음
            if r_values[best_fit] >= 0.8:
                return best_fit
            else:
                return None
                
        except Exception as e:
            return None
    
    def estimate_space_complexity(self, source_code: str, source_lines: int, memory_mb: Optional[float]) -> str:
        """공간복잡도 추정"""
        if not source_code:
            # 소스 코드가 없으면 소스 라인 수 기반으로 기본 추정
            if source_lines < 10:
                return "O(1)"
            elif source_lines < 30:
                return "O(n)"
            elif source_lines < 100:
                return "O(n)"
            else:
                return "O(n²)"
        
        try:
            # 리스트, 딕셔너리, 배열 등의 자료구조 사용 패턴 분석
            has_list_comp = '[' in source_code and 'for' in source_code
            has_dict_comp = '{' in source_code and 'for' in source_code
            has_nested_list = source_code.count('[') >= 3
            has_recursion = False
            
            # 재귀 함수 체크
            func_def_match = re.search(r'def\s+(\w+)', source_code)
            if func_def_match:
                func_name = func_def_match.group(1)
                func_body = source_code.split(':', 1)[1] if ':' in source_code else source_code
                has_recursion = func_name in func_body or f'self.{func_name}' in func_body
            
            # 중첩 루프 개수
            lines = source_code.split('\n')
            indent_levels = []
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith('for ') or stripped.startswith('while '):
                    indent = len(line) - len(stripped)
                    indent_levels.append(indent)
            
            nested_loops = len(set(indent_levels)) if len(indent_levels) > 1 else 0
            
            # 공간복잡도 추정
            if nested_loops >= 3 or has_nested_list:
                return "O(n³+)"
            elif nested_loops == 2 or (has_list_comp and has_dict_comp):
                return "O(n²)"
            elif has_list_comp or has_dict_comp or nested_loops == 1:
                return "O(n)"
            elif has_recursion:
                return "O(log n)"
            else:
                return "O(1)"
                
        except Exception as e:
            # 예외 발생 시 소스 라인 수 기반으로 기본 추정
            if source_lines < 10:
                return "O(1)"
            elif source_lines < 30:
                return "O(n)"
            elif source_lines < 100:
                return "O(n)"
            else:
                return "O(n²)"
    
    def analyze_all_functions(self):
        """모든 함수 분석"""
        print("\n" + "="*60)
        print("함수 분석 시작")
        print("="*60)
        
        # 일반 함수 분석
        for func_name, func_info in self.functions.items():
            print(f"\n📊 분석 중: {func_name}()")
            result = self._analyze_single_function(func_name, func_info, None)
            self.results.append(result)
        
        # 클래스 메서드 분석 (소스 코드 분석만 수행)
        for class_name, class_info in self.classes.items():
            print(f"\n📦 클래스: {class_name}")
            
            for method_name, method_info in class_info['methods'].items():
                full_name = f"{class_name}.{method_name}"
                print(f"  📊 분석 중: {full_name}()")
                result = self._analyze_single_function(full_name, method_info, None)
                self.results.append(result)
        
        print("\n" + "="*60)
        print(f"✅ 분석 완료: 총 {len(self.results)}개 함수")
        print("="*60)
    
    def _analyze_single_function(self, name: str, func_info: dict, instance: Any = None) -> Dict:
        """단일 함수 분석 (소스 코드 분석만 수행, 실제 실행 없음)"""
        result = {
            'name': name,
            'type': func_info['type'],
            'signature': func_info['signature'],
            'source_lines': func_info['source_lines'],
            'execution_time': {'note': '소스 코드 분석만 수행 (실제 실행 안 함)'},
            'memory_usage': {'note': '소스 코드 분석만 수행 (실제 실행 안 함)'},
            'time_complexity': 'N/A',
            'space_complexity': 'N/A'
        }
        
        source_code = func_info.get('source_code', '')
        
        # 정적 분석으로 시간복잡도 추정
        result['time_complexity'] = self.estimate_time_complexity_static(source_code, result['source_lines'])
        
        # 공간복잡도 추정
        result['space_complexity'] = self.estimate_space_complexity(source_code, result['source_lines'], None)
        
        return result


class ReportGenerator:
    """마크다운 보고서 생성 클래스"""
    
    def __init__(self, results: List[Dict], file_path: str, output_dir: str):
        self.results = results
        self.file_path = Path(file_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_filename = f"time_{self.file_path.stem}"
        
    def generate_report(self) -> str:
        """전체 보고서 생성"""
        report_path = self.output_dir / f"{self.base_filename}_{self.timestamp}.md"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            # 헤더
            f.write(self._generate_header())
            
            # 요약
            f.write(self._generate_summary())
            
            # 병목 구간
            f.write(self._generate_bottlenecks())
            
            # 상세 테이블
            f.write(self._generate_summary_table())
            
            # 상세 분석
            f.write(self._generate_detailed_report())
            
            # 푸터
            f.write(self._generate_footer())
        
        print(f"\n✅ 보고서 생성 완료: {report_path}")
        return str(report_path)
    
    def _generate_header(self) -> str:
        """헤더 생성"""
        return f"""# Performance Analysis Report

**분석 파일**: `{self.file_path.name}`  
**파일 경로**: `{self.file_path}`  
**분석 일시**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**총 분석 함수**: {len(self.results)}개

---

"""
    
    def _generate_summary(self) -> str:
        """요약 생성"""
        analyzed = [r for r in self.results if r.get('time_complexity') and r['time_complexity'] != 'N/A']
        
        # 복잡도별 분류
        complexity_count = {}
        for r in analyzed:
            complexity = r.get('time_complexity', 'N/A')
            complexity_count[complexity] = complexity_count.get(complexity, 0) + 1
        
        complexity_summary = ", ".join([f"{k}: {v}개" for k, v in complexity_count.items()])
        
        return f"""## 📊 분석 요약

- **총 분석 함수**: {len(self.results)}개
- **복잡도 분석 완료**: {len(analyzed)}개
- **복잡도 분포**: {complexity_summary}

**참고**: 이 보고서는 소스 코드 정적 분석만 수행했습니다. 실제 실행은 하지 않았습니다.

---

"""
    
    def _generate_bottlenecks(self) -> str:
        """병목 구간 식별 (복잡도 기준)"""
        def complexity_to_priority(complexity: str) -> int:
            """복잡도를 우선순위 점수로 변환 (높을수록 병목)"""
            if not complexity or complexity == 'N/A':
                return 0
            complexity_lower = complexity.lower()
            if 'o(n³' in complexity_lower or 'o(n^3)' in complexity_lower:
                return 6
            elif 'o(n²)' in complexity_lower or 'o(n^2)' in complexity_lower:
                return 5
            elif 'o(n log n)' in complexity_lower:
                return 4
            elif 'o(n)' in complexity_lower and 'log' not in complexity_lower:
                return 3
            elif 'o(log n)' in complexity_lower:
                return 2
            elif 'o(1)' in complexity_lower:
                return 1
            return 0
        
        # 시간복잡도 기준 정렬
        analyzed = [r for r in self.results if r.get('time_complexity') and r['time_complexity'] != 'N/A']
        sorted_by_complexity = sorted(analyzed, key=lambda x: complexity_to_priority(x.get('time_complexity', 'N/A')), reverse=True)
        
        top_5_complexity = sorted_by_complexity[:5]
        
        report = """## 🔴 병목 구간 (시간복잡도 기준 Top 5)

| 순위 | 함수명 | 시간복잡도 | 공간복잡도 | 소스 라인 수 |
|------|--------|-----------|-----------|------------|
"""
        
        for i, result in enumerate(top_5_complexity, 1):
            name = result['name']
            time_complexity = result.get('time_complexity', 'N/A')
            space_complexity = result.get('space_complexity', 'N/A')
            source_lines = result.get('source_lines', 0)
            
            report += f"| {i} | `{name}` | {time_complexity} | {space_complexity} | {source_lines}줄 |\n"
        
        report += "\n---\n\n"
        return report
    
    def _generate_summary_table(self) -> str:
        """요약 테이블 생성"""
        report = """## 📋 전체 함수 분석 결과

| 함수명 | 타입 | 시간복잡도 | 공간복잡도 | 소스 라인 수 | 상태 |
|--------|------|-----------|-----------|------------|------|
"""
        
        for result in self.results:
            name = result['name']
            func_type = result['type']
            time_complexity = result.get('time_complexity', 'N/A')
            space_complexity = result.get('space_complexity', 'N/A')
            source_lines = result.get('source_lines', 0)
            
            if time_complexity != 'N/A' and space_complexity != 'N/A':
                status = "✅"
            else:
                status = "⚠️"
            
            report += f"| `{name}` | {func_type} | {time_complexity} | {space_complexity} | {source_lines}줄 | {status} |\n"
        
        report += "\n---\n\n"
        return report
    
    def _generate_detailed_report(self) -> str:
        """상세 분석 보고서"""
        report = "## 📖 상세 분석\n\n"
        
        for result in self.results:
            report += f"### `{result['name']}`\n\n"
            report += f"- **타입**: {result['type']}\n"
            report += f"- **시그니처**: `{result['signature']}`\n"
            report += f"- **소스 라인 수**: {result['source_lines']}줄\n\n"
            
            report += "**복잡도 분석**:\n"
            report += f"- **시간복잡도**: {result.get('time_complexity', 'N/A')}\n"
            report += f"- **공간복잡도**: {result.get('space_complexity', 'N/A')}\n\n"
            
            report += "---\n\n"
        
        return report
    
    def _generate_footer(self) -> str:
        """푸터 생성"""
        return f"""## 📝 참고사항

- 이 보고서는 **소스 코드 정적 분석만** 수행했습니다. 실제 함수 실행은 하지 않았습니다.
- 시간복잡도는 소스 코드의 루프 패턴, 재귀 호출, 중첩 레벨 등을 분석하여 추정되었습니다.
- 공간복잡도는 소스 코드의 자료구조 사용 패턴을 분석하여 추정되었습니다.
- 복잡도 추정값은 실제와 다를 수 있습니다.
- 실제 실행 시간과 메모리 사용량은 측정되지 않았습니다.

---

**생성 도구**: Performance Analysis Tool (정적 분석 모드)  
**생성 일시**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    
    def identify_bottlenecks(self) -> List[Dict]:
        """병목 구간 식별 (복잡도 기준)"""
        def complexity_to_priority(complexity: str) -> int:
            """복잡도를 우선순위 점수로 변환"""
            if not complexity or complexity == 'N/A':
                return 0
            complexity_lower = complexity.lower()
            if 'o(n³' in complexity_lower or 'o(n^3)' in complexity_lower:
                return 6
            elif 'o(n²)' in complexity_lower or 'o(n^2)' in complexity_lower:
                return 5
            elif 'o(n log n)' in complexity_lower:
                return 4
            elif 'o(n)' in complexity_lower and 'log' not in complexity_lower:
                return 3
            elif 'o(log n)' in complexity_lower:
                return 2
            elif 'o(1)' in complexity_lower:
                return 1
            return 0
        
        analyzed = [r for r in self.results if r.get('time_complexity') and r['time_complexity'] != 'N/A']
        sorted_by_complexity = sorted(analyzed, key=lambda x: complexity_to_priority(x.get('time_complexity', 'N/A')), reverse=True)
        return sorted_by_complexity[:5]


def main():
    """메인 실행 함수"""
    print("="*60)
    print("Performance Analysis Tool")
    print("="*60)
    print()
    
    # 사용자 입력
    file_path = input("분석할 Python 파일의 절대 경로를 입력하세요: ").strip()
    
    if not file_path:
        print("❌ 파일 경로가 입력되지 않았습니다.")
        return
    
    # 따옴표 제거
    file_path = file_path.strip('"').strip("'")
    
    # 분석기 초기화
    analyzer = FunctionAnalyzer(file_path)
    
    # 모듈 로드
    if not analyzer.load_module():
        return
    
    # 함수 추출
    analyzer.extract_functions()
    
    if not analyzer.functions and not analyzer.classes:
        print("❌ 분석할 함수를 찾을 수 없습니다.")
        return
    
    # 함수 분석
    analyzer.analyze_all_functions()
    
    # 보고서 생성
    output_dir = Path(__file__).parent.parent / "time_test"
    generator = ReportGenerator(analyzer.results, file_path, str(output_dir))
    report_path = generator.generate_report()
    
    print(f"\n✅ 분석 완료!")
    print(f"📄 보고서 위치: {report_path}")
    
    # 병목 구간 출력
    bottlenecks = generator.identify_bottlenecks()
    if bottlenecks:
        print("\n🔴 병목 구간 Top 5 (시간복잡도 기준):")
        for i, result in enumerate(bottlenecks, 1):
            print(f"  {i}. {result['name']}: {result.get('time_complexity', 'N/A')}")


if __name__ == "__main__":
    main()

