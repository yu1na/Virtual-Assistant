#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG 평가 결과 시각화 스크립트

evaluation_results.json 파일을 읽어서 다양한 차트와 그래프로 시각화합니다.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import pandas as pd
import numpy as np

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

# ============================================================================
# 설정
# ============================================================================
RESULTS_FILE = "backend/app/domain/rag/Insurance/tests/evaluation_results.json"
OUTPUT_DIR = "backend/app/domain/rag/Insurance/tests/visualizations"

# 한글 폰트 설정
def setup_korean_font():
    """한글 폰트 설정 (Windows 환경)"""
    if sys.platform == 'win32':
        # Windows의 기본 한글 폰트 사용
        font_names = ['Malgun Gothic', 'NanumGothic', 'NanumBarunGothic', 'Gulim']
        for font_name in font_names:
            try:
                plt.rcParams['font.family'] = font_name
                plt.rcParams['axes.unicode_minus'] = False
                print(f"[OK] 한글 폰트 설정: {font_name}")
                return
            except:
                continue
    
    # 기본 설정
    plt.rcParams['axes.unicode_minus'] = False
    print("[INFO] 기본 폰트 사용")

# Seaborn 스타일 설정
sns.set_style("whitegrid")
sns.set_palette("husl")


# ============================================================================
# 데이터 로드
# ============================================================================
def load_results(file_path: str) -> Dict[str, Any]:
    """평가 결과 JSON 파일 로드"""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"결과 파일을 찾을 수 없습니다: {abs_path}")
    
    with open(abs_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"[OK] 평가 결과 로드 완료: {len(data['detailed_results'])}개 항목")
    return data


# ============================================================================
# 시각화 함수들
# ============================================================================

def plot_overall_metrics(summary: Dict[str, Any], output_dir: str):
    """전체 성능 지표 바차트"""
    metrics = {
        'Retrieval\nHit Rate': summary['retrieval_hit_rate'],
        'Semantic\nSimilarity': summary['semantic_similarity_avg'],
        'Similarity\nHit Rate': summary['similarity_hit_rate'],
        'Judge Score\n(normalized)': summary['judge_score_avg'] / 2.0,
        'Keyword\nHit Rate': summary['keyword_hit_rate']
    }
    
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(metrics.keys(), metrics.values(), color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'])
    
    # 값 표시
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2%}' if height <= 1 else f'{height:.2f}',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_ylabel('Score / Rate', fontsize=12)
    ax.set_title('RAG System Overall Performance Metrics', fontsize=14, fontweight='bold')
    ax.set_ylim(0, 1.1)
    ax.axhline(y=0.75, color='red', linestyle='--', alpha=0.5, label='Target (75%)')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '01_overall_metrics.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 전체 성능 지표 차트 생성")


def plot_score_distribution(results: List[Dict[str, Any]], output_dir: str):
    """점수 분포 히스토그램"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Semantic Similarity 분포
    similarities = [r['semantic_similarity'] for r in results]
    axes[0, 0].hist(similarities, bins=20, color='#4ECDC4', edgecolor='black', alpha=0.7)
    axes[0, 0].axvline(x=0.75, color='red', linestyle='--', label='Threshold (0.75)')
    axes[0, 0].set_xlabel('Semantic Similarity', fontsize=10)
    axes[0, 0].set_ylabel('Frequency', fontsize=10)
    axes[0, 0].set_title('Semantic Similarity Distribution', fontsize=12, fontweight='bold')
    axes[0, 0].legend()
    
    # Judge Score 분포
    judge_scores = [r['judge_score'] for r in results]
    score_counts = pd.Series(judge_scores).value_counts().sort_index()
    axes[0, 1].bar(score_counts.index, score_counts.values, color=['#FF6B6B', '#FFA07A', '#98D8C8'], edgecolor='black')
    axes[0, 1].set_xlabel('Judge Score', fontsize=10)
    axes[0, 1].set_ylabel('Frequency', fontsize=10)
    axes[0, 1].set_title('LLM Judge Score Distribution', fontsize=12, fontweight='bold')
    axes[0, 1].set_xticks([0, 1, 2])
    
    # Keyword Count 분포
    keyword_counts = [r['keyword_count'] for r in results]
    axes[1, 0].hist(keyword_counts, bins=range(0, max(keyword_counts)+2), color='#45B7D1', edgecolor='black', alpha=0.7)
    axes[1, 0].axvline(x=2, color='red', linestyle='--', label='Min Threshold (2)')
    axes[1, 0].set_xlabel('Keyword Hit Count', fontsize=10)
    axes[1, 0].set_ylabel('Frequency', fontsize=10)
    axes[1, 0].set_title('Keyword Hit Count Distribution', fontsize=12, fontweight='bold')
    axes[1, 0].legend()
    
    # Retrieved Chunks 분포
    chunk_counts = [r['num_retrieved_chunks'] for r in results]
    axes[1, 1].hist(chunk_counts, bins=range(0, max(chunk_counts)+2), color='#FFA07A', edgecolor='black', alpha=0.7)
    axes[1, 1].set_xlabel('Number of Retrieved Chunks', fontsize=10)
    axes[1, 1].set_ylabel('Frequency', fontsize=10)
    axes[1, 1].set_title('Retrieved Chunks Distribution', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '02_score_distributions.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 점수 분포 차트 생성")


def plot_hit_rates_comparison(summary: Dict[str, Any], output_dir: str):
    """각 지표별 Hit/Miss 비교 파이차트"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    metrics = [
        ('Retrieval Hit', summary['retrieval_hit_count'], summary['total_questions']),
        ('Similarity Hit', summary['similarity_hit_count'], summary['total_questions']),
        ('Keyword Hit', summary['keyword_hit_count'], summary['total_questions'])
    ]
    
    colors_hit = ['#98D8C8', '#FFE5E5']
    
    for idx, (title, hit_count, total) in enumerate(metrics):
        miss_count = total - hit_count
        sizes = [hit_count, miss_count]
        labels = [f'Hit ({hit_count})', f'Miss ({miss_count})']
        
        axes[idx].pie(sizes, labels=labels, colors=colors_hit, autopct='%1.1f%%',
                     startangle=90, textprops={'fontsize': 10})
        axes[idx].set_title(f'{title}\n({hit_count}/{total})', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '03_hit_rates_comparison.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Hit Rate 비교 차트 생성")


def plot_correlation_heatmap(results: List[Dict[str, Any]], output_dir: str):
    """지표 간 상관관계 히트맵"""
    df = pd.DataFrame(results)
    
    # 숫자형 컬럼만 선택
    numeric_cols = ['semantic_similarity', 'judge_score', 'keyword_count', 
                   'retrieval_hit', 'similarity_hit', 'keyword_hit']
    df_numeric = df[numeric_cols].astype(float)
    
    # 상관관계 계산
    corr = df_numeric.corr()
    
    # 히트맵 그리기
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                square=True, linewidths=1, cbar_kws={"shrink": 0.8},
                ax=ax, vmin=-1, vmax=1)
    
    ax.set_title('Correlation Between Evaluation Metrics', fontsize=14, fontweight='bold')
    
    # 레이블 개선
    labels = ['Semantic\nSimilarity', 'Judge\nScore', 'Keyword\nCount',
             'Retrieval\nHit', 'Similarity\nHit', 'Keyword\nHit']
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_yticklabels(labels, rotation=0)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '04_correlation_heatmap.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 상관관계 히트맵 생성")


def plot_performance_by_question(results: List[Dict[str, Any]], output_dir: str):
    """질문별 성능 추이 라인차트 (상위 20개)"""
    df = pd.DataFrame(results[:20])  # 처음 20개만
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = range(len(df))
    ax.plot(x, df['semantic_similarity'], marker='o', label='Semantic Similarity', linewidth=2)
    ax.plot(x, df['judge_score'] / 2.0, marker='s', label='Judge Score (normalized)', linewidth=2)
    ax.scatter(x, df['retrieval_hit'], marker='^', s=100, label='Retrieval Hit', alpha=0.6)
    
    ax.axhline(y=0.75, color='red', linestyle='--', alpha=0.5, label='Target (75%)')
    
    ax.set_xlabel('Question Index', fontsize=11)
    ax.set_ylabel('Score', fontsize=11)
    ax.set_title('Performance Trend by Question (First 20)', fontsize=13, fontweight='bold')
    ax.set_ylim(-0.1, 1.1)
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '05_performance_trend.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 질문별 성능 추이 차트 생성")


def plot_failure_analysis(summary: Dict[str, Any], results: List[Dict[str, Any]], output_dir: str):
    """실패 사례 분석"""
    failures = summary.get('failures', [])
    
    if not failures:
        print("[INFO] 실패 사례가 없어 분석 차트를 생성하지 않습니다.")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # 실패 vs 성공 비율
    success_count = summary['total_questions'] - summary['failure_count']
    failure_count = summary['failure_count']
    
    axes[0].pie([success_count, failure_count], 
               labels=[f'Success ({success_count})', f'Failure ({failure_count})'],
               colors=['#98D8C8', '#FF6B6B'],
               autopct='%1.1f%%', startangle=90, textprops={'fontsize': 11})
    axes[0].set_title('Success vs Failure Rate', fontsize=12, fontweight='bold')
    
    # 실패 사례의 Semantic Similarity 분포
    if failures:
        failure_sims = [f['semantic_similarity'] for f in failures]
        axes[1].hist(failure_sims, bins=10, color='#FF6B6B', edgecolor='black', alpha=0.7)
        axes[1].axvline(x=np.mean(failure_sims), color='blue', linestyle='--', 
                       label=f'Mean: {np.mean(failure_sims):.2f}')
        axes[1].set_xlabel('Semantic Similarity', fontsize=10)
        axes[1].set_ylabel('Frequency', fontsize=10)
        axes[1].set_title('Semantic Similarity of Failed Cases', fontsize=12, fontweight='bold')
        axes[1].legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '06_failure_analysis.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 실패 사례 분석 차트 생성")


def plot_summary_table(summary: Dict[str, Any], output_dir: str):
    """요약 테이블 이미지"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    
    # 테이블 데이터 준비
    table_data = [
        ['Metric', 'Value', 'Rate/Score'],
        ['Total Questions', f"{summary['total_questions']}", '-'],
        ['Retrieval Hit', f"{summary['retrieval_hit_count']}/{summary['total_questions']}", 
         f"{summary['retrieval_hit_rate']:.1%}"],
        ['Semantic Similarity (avg)', '-', f"{summary['semantic_similarity_avg']:.3f}"],
        ['Similarity Hit (≥0.75)', f"{summary['similarity_hit_count']}/{summary['total_questions']}", 
         f"{summary['similarity_hit_rate']:.1%}"],
        ['Judge Score (avg)', '-', f"{summary['judge_score_avg']:.2f}/2.0"],
        ['Keyword Hit', f"{summary['keyword_hit_count']}/{summary['total_questions']}", 
         f"{summary['keyword_hit_rate']:.1%}"],
        ['Failure Count', f"{summary['failure_count']}", 
         f"{summary['failure_count']/summary['total_questions']:.1%}"]
    ]
    
    table = ax.table(cellText=table_data, cellLoc='center', loc='center',
                    colWidths=[0.4, 0.3, 0.3])
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.5)
    
    # 헤더 스타일
    for i in range(3):
        table[(0, i)].set_facecolor('#4ECDC4')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # 행 색상 교대
    for i in range(1, len(table_data)):
        for j in range(3):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#F0F0F0')
    
    ax.set_title('RAG Performance Summary', fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '00_summary_table.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 요약 테이블 생성")


def create_comprehensive_report(results: List[Dict[str, Any]], output_dir: str):
    """종합 리포트 (단일 페이지에 여러 차트)"""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. 전체 성능 지표 (왼쪽 상단)
    ax1 = fig.add_subplot(gs[0, :2])
    df = pd.DataFrame(results)
    metrics_summary = {
        'Retrieval Hit': df['retrieval_hit'].mean(),
        'Semantic Sim': df['semantic_similarity'].mean(),
        'Similarity Hit': df['similarity_hit'].mean(),
        'Judge Score': df['judge_score'].mean() / 2.0,
        'Keyword Hit': df['keyword_hit'].mean()
    }
    bars = ax1.barh(list(metrics_summary.keys()), list(metrics_summary.values()), 
                    color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'])
    ax1.set_xlim(0, 1.1)
    ax1.set_xlabel('Score / Rate')
    ax1.set_title('Overall Performance Metrics', fontweight='bold')
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax1.text(width + 0.02, bar.get_y() + bar.get_height()/2, 
                f'{width:.2%}', va='center', fontsize=9)
    
    # 2. Judge Score 분포 (오른쪽 상단)
    ax2 = fig.add_subplot(gs[0, 2])
    judge_scores = df['judge_score'].value_counts().sort_index()
    ax2.bar(judge_scores.index, judge_scores.values, color=['#FF6B6B', '#FFA07A', '#98D8C8'])
    ax2.set_title('Judge Score Dist.', fontweight='bold', fontsize=10)
    ax2.set_xlabel('Score', fontsize=9)
    ax2.set_xticks([0, 1, 2])
    
    # 3. Semantic Similarity 분포 (중앙 왼쪽)
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.hist(df['semantic_similarity'], bins=15, color='#4ECDC4', edgecolor='black', alpha=0.7)
    ax3.axvline(x=0.75, color='red', linestyle='--', linewidth=1)
    ax3.set_title('Semantic Similarity', fontweight='bold', fontsize=10)
    ax3.set_xlabel('Similarity', fontsize=9)
    
    # 4. Keyword Count 분포 (중앙 중간)
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.hist(df['keyword_count'], bins=range(0, int(df['keyword_count'].max())+2), 
            color='#45B7D1', edgecolor='black', alpha=0.7)
    ax4.axvline(x=2, color='red', linestyle='--', linewidth=1)
    ax4.set_title('Keyword Count', fontweight='bold', fontsize=10)
    ax4.set_xlabel('Count', fontsize=9)
    
    # 5. Hit Rates 비교 (중앙 오른쪽)
    ax5 = fig.add_subplot(gs[1, 2])
    hit_rates = {
        'Retrieval': df['retrieval_hit'].mean(),
        'Similarity': df['similarity_hit'].mean(),
        'Keyword': df['keyword_hit'].mean()
    }
    ax5.bar(hit_rates.keys(), hit_rates.values(), color=['#FF6B6B', '#4ECDC4', '#98D8C8'])
    ax5.set_ylim(0, 1.1)
    ax5.set_title('Hit Rates Comparison', fontweight='bold', fontsize=10)
    ax5.set_ylabel('Rate', fontsize=9)
    for i, (k, v) in enumerate(hit_rates.items()):
        ax5.text(i, v + 0.02, f'{v:.1%}', ha='center', fontsize=9)
    
    # 6. 성능 추이 (하단 전체)
    ax6 = fig.add_subplot(gs[2, :])
    x = range(min(30, len(df)))
    sample_df = df.iloc[:30]
    ax6.plot(x, sample_df['semantic_similarity'], marker='o', label='Sem. Similarity', linewidth=1.5, markersize=3)
    ax6.plot(x, sample_df['judge_score'] / 2.0, marker='s', label='Judge Score', linewidth=1.5, markersize=3)
    ax6.scatter(x, sample_df['retrieval_hit'], marker='^', s=50, label='Retrieval Hit', alpha=0.6)
    ax6.axhline(y=0.75, color='red', linestyle='--', alpha=0.5)
    ax6.set_xlabel('Question Index', fontsize=9)
    ax6.set_ylabel('Score', fontsize=9)
    ax6.set_title('Performance Trend (First 30 Questions)', fontweight='bold', fontsize=10)
    ax6.legend(loc='lower right', fontsize=8)
    ax6.grid(True, alpha=0.3)
    ax6.set_ylim(-0.1, 1.1)
    
    fig.suptitle('RAG Performance Comprehensive Report', fontsize=16, fontweight='bold', y=0.98)
    
    plt.savefig(os.path.join(output_dir, '07_comprehensive_report.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 종합 리포트 생성")


# ============================================================================
# 메인 실행
# ============================================================================
def main():
    """메인 실행 함수"""
    print("="*80)
    print("RAG 평가 결과 시각화")
    print("="*80)
    
    # 1. 한글 폰트 설정
    setup_korean_font()
    
    # 2. 결과 로드
    print("\n[1] 결과 파일 로드 중...")
    data = load_results(RESULTS_FILE)
    summary = data['summary']
    results = data['detailed_results']
    
    # 3. 출력 디렉토리 생성
    output_dir = os.path.abspath(OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[2] 출력 디렉토리: {output_dir}")
    
    # 4. 시각화 생성
    print("\n[3] 시각화 생성 중...")
    print("-" * 80)
    
    plot_summary_table(summary, output_dir)
    plot_overall_metrics(summary, output_dir)
    plot_score_distribution(results, output_dir)
    plot_hit_rates_comparison(summary, output_dir)
    plot_correlation_heatmap(results, output_dir)
    plot_performance_by_question(results, output_dir)
    plot_failure_analysis(summary, results, output_dir)
    create_comprehensive_report(results, output_dir)
    
    print("-" * 80)
    print(f"\n[OK] 시각화 완료! 총 8개 이미지 생성")
    print(f"\n저장 위치: {output_dir}")
    print("\n생성된 파일:")
    print("  - 00_summary_table.png          : 요약 테이블")
    print("  - 01_overall_metrics.png        : 전체 성능 지표")
    print("  - 02_score_distributions.png    : 점수 분포")
    print("  - 03_hit_rates_comparison.png   : Hit Rate 비교")
    print("  - 04_correlation_heatmap.png    : 상관관계 히트맵")
    print("  - 05_performance_trend.png      : 질문별 성능 추이")
    print("  - 06_failure_analysis.png       : 실패 사례 분석")
    print("  - 07_comprehensive_report.png   : 종합 리포트")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
