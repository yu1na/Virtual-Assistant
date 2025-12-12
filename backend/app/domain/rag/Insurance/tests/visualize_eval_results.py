#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG 평가 결과 시각화 스크립트

results/eval_*.json 파일들을 읽어서 다양한 차트와 그래프로 시각화합니다.
"""

import os
import sys
import json
import glob
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
RESULTS_DIR = "backend/app/domain/rag/Insurance/tests/results"
OUTPUT_DIR = "backend/app/domain/rag/Insurance/tests/visualizations"

# 한글 폰트 설정
def setup_korean_font():
    """한글 폰트 설정"""
    if sys.platform == 'darwin':  # macOS
        plt.rcParams['font.family'] = 'AppleGothic'
    elif sys.platform == 'win32':
        font_names = ['Malgun Gothic', 'NanumGothic', 'NanumBarunGothic', 'Gulim']
        for font_name in font_names:
            try:
                plt.rcParams['font.family'] = font_name
                break
            except:
                continue
    else:  # Linux
        plt.rcParams['font.family'] = 'DejaVu Sans'
    
    plt.rcParams['axes.unicode_minus'] = False
    print("[OK] 폰트 설정 완료")

# Seaborn 스타일 설정
sns.set_style("whitegrid")
sns.set_palette("husl")


# ============================================================================
# 데이터 로드
# ============================================================================
def load_result_files(results_dir: str) -> List[Dict[str, Any]]:
    """결과 파일들 로드"""
    pattern = os.path.join(results_dir, 'eval_*.json')
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"결과 파일을 찾을 수 없습니다: {pattern}")
    
    results = []
    for file_path in sorted(files):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data['_filepath'] = file_path
            data['_filename'] = os.path.basename(file_path)
            results.append(data)
    
    print(f"[OK] {len(results)}개의 결과 파일 로드 완료")
    for r in results:
        print(f"     - {r['_filename']}: avg_sim={r['summary']['avg_similarity']:.3f}, total={r['summary']['total']}")
    return results


# ============================================================================
# 단일 결과 시각화
# ============================================================================

def plot_single_summary(data: Dict[str, Any], output_dir: str, suffix: str = ""):
    """단일 결과의 요약 테이블"""
    summary = data['summary']
    config = data.get('config', {})
    
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.axis('off')
    
    # 테이블 데이터
    table_data = [
        ['Metric', 'Value'],
        ['Embedding Model', config.get('embedding_model', 'N/A')],
        ['LLM Model', config.get('llm_model', 'N/A')],
        ['Top-K', str(config.get('top_k', 'N/A'))],
        ['Hybrid Ratio', str(config.get('hybrid_ratio', 'N/A'))],
        ['Sample Size', str(summary['total'])],
        ['', ''],
        ['Average Similarity', f"{summary['avg_similarity']:.4f}"],
        ['Median Similarity', f"{summary['median_similarity']:.4f}"],
        ['Std Similarity', f"{summary['std_similarity']:.4f}"],
        ['Min Similarity', f"{summary['min_similarity']:.4f}"],
        ['Max Similarity', f"{summary['max_similarity']:.4f}"],
        ['', ''],
        ['≥ 0.5 Threshold', f"{summary['threshold_0.5']}/{summary['total']} ({summary['threshold_0.5']/summary['total']:.1%})"],
        ['≥ 0.6 Threshold', f"{summary['threshold_0.6']}/{summary['total']} ({summary['threshold_0.6']/summary['total']:.1%})"],
        ['≥ 0.7 Threshold', f"{summary['threshold_0.7']}/{summary['total']} ({summary['threshold_0.7']/summary['total']:.1%})"],
    ]
    
    table = ax.table(cellText=table_data, cellLoc='left', loc='center',
                    colWidths=[0.5, 0.5])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2.2)
    
    # 헤더 스타일
    for i in range(2):
        table[(0, i)].set_facecolor('#4ECDC4')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # 행 색상
    for i in range(1, len(table_data)):
        for j in range(2):
            if table_data[i][0] == '':
                table[(i, j)].set_facecolor('#FFFFFF')
            elif i % 2 == 0:
                table[(i, j)].set_facecolor('#F0F0F0')
    
    title = f"RAG Performance Summary{suffix}"
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    filename = f"01_summary_table{suffix}.png"
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] {filename} 생성")


def plot_similarity_distribution(data: Dict[str, Any], output_dir: str, suffix: str = ""):
    """유사도 분포 히스토그램"""
    results = data['results']
    similarities = [r['similarity'] for r in results]
    summary = data['summary']
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 히스토그램
    ax.hist(similarities, bins=20, color='#4ECDC4', edgecolor='black', alpha=0.7, label='Distribution')
    
    # 평균선
    ax.axvline(x=summary['avg_similarity'], color='blue', linestyle='--', linewidth=2, 
              label=f"Mean: {summary['avg_similarity']:.3f}")
    
    # 중앙값선
    ax.axvline(x=summary['median_similarity'], color='green', linestyle='--', linewidth=2,
              label=f"Median: {summary['median_similarity']:.3f}")
    
    # 임계값
    ax.axvline(x=0.5, color='orange', linestyle=':', linewidth=1.5, alpha=0.7, label='Threshold (0.5)')
    ax.axvline(x=0.7, color='red', linestyle=':', linewidth=1.5, alpha=0.7, label='Threshold (0.7)')
    
    ax.set_xlabel('Semantic Similarity', fontsize=11)
    ax.set_ylabel('Frequency', fontsize=11)
    ax.set_title('Semantic Similarity Distribution', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    filename = f"02_similarity_distribution{suffix}.png"
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] {filename} 생성")


def plot_threshold_comparison(data: Dict[str, Any], output_dir: str, suffix: str = ""):
    """임계값별 통과율 비교"""
    summary = data['summary']
    total = summary['total']
    
    thresholds = [0.5, 0.6, 0.7, 0.8]
    counts = [
        summary.get('threshold_0.5', 0),
        summary.get('threshold_0.6', 0),
        summary.get('threshold_0.7', 0),
        len([r for r in data['results'] if r['similarity'] >= 0.8])
    ]
    rates = [c/total for c in counts]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    
    # 바차트 (개수)
    bars = ax1.bar([f'≥{t}' for t in thresholds], counts, 
                   color=['#98D8C8', '#4ECDC4', '#45B7D1', '#FFA07A'])
    ax1.set_ylabel('Count', fontsize=11)
    ax1.set_title('Absolute Count by Threshold', fontsize=12, fontweight='bold')
    ax1.set_ylim(0, total * 1.1)
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 파이차트 (비율)
    colors = ['#98D8C8', '#4ECDC4', '#45B7D1', '#FFA07A']
    labels = [f'≥{t}\n({c}/{total})' for t, c in zip(thresholds, counts)]
    ax2.pie(counts, labels=labels, colors=colors, autopct='%1.1f%%',
           startangle=90, textprops={'fontsize': 10})
    ax2.set_title('Distribution by Threshold', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    filename = f"03_threshold_comparison{suffix}.png"
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] {filename} 생성")


def plot_performance_trend(data: Dict[str, Any], output_dir: str, suffix: str = ""):
    """성능 추이 라인차트"""
    results = data['results']
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = range(len(results))
    similarities = [r['similarity'] for r in results]
    
    ax.plot(x, similarities, marker='o', markersize=4, linewidth=1.5, color='#4ECDC4', label='Similarity')
    ax.fill_between(x, similarities, alpha=0.3, color='#4ECDC4')
    
    # 롤링 평균
    if len(results) > 10:
        rolling_avg = pd.Series(similarities).rolling(window=5, center=True).mean()
        ax.plot(x, rolling_avg, linewidth=2, color='#FF6B6B', label='5-point Moving Avg')
    
    # 임계값
    ax.axhline(y=0.7, color='red', linestyle='--', alpha=0.5, label='Target (0.7)')
    ax.axhline(y=0.5, color='orange', linestyle='--', alpha=0.5, label='Minimum (0.5)')
    
    ax.set_xlabel('Question Index', fontsize=11)
    ax.set_ylabel('Similarity Score', fontsize=11)
    ax.set_title('Performance Trend Across Questions', fontsize=13, fontweight='bold')
    ax.set_ylim(-0.1, 1.1)
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    
    filename = f"04_performance_trend{suffix}.png"
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] {filename} 생성")


def plot_top_bottom_cases(data: Dict[str, Any], output_dir: str, suffix: str = ""):
    """상위/하위 사례"""
    results = data['results']
    
    # 상위 5개
    sorted_by_sim = sorted(results, key=lambda x: x['similarity'], reverse=True)
    top_5 = sorted_by_sim[:5]
    bottom_5 = sorted_by_sim[-5:]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))
    
    # 상위 5개
    labels_top = [f"Q{i+1}" for i in range(len(top_5))]
    scores_top = [r['similarity'] for r in top_5]
    bars1 = ax1.barh(labels_top, scores_top, color='#98D8C8')
    ax1.set_xlabel('Similarity', fontsize=11)
    ax1.set_title('Top 5 Performing Cases', fontsize=12, fontweight='bold')
    ax1.set_xlim(0, 1.1)
    for i, bar in enumerate(bars1):
        width = bar.get_width()
        ax1.text(width + 0.02, bar.get_y() + bar.get_height()/2,
                f'{width:.3f}', va='center', fontsize=9)
    
    # 하위 5개
    labels_bottom = [f"Q{i+1}" for i in range(len(bottom_5))]
    scores_bottom = [r['similarity'] for r in bottom_5]
    bars2 = ax2.barh(labels_bottom, scores_bottom, color='#FF6B6B')
    ax2.set_xlabel('Similarity', fontsize=11)
    ax2.set_title('Bottom 5 Performing Cases', fontsize=12, fontweight='bold')
    ax2.set_xlim(0, 1.1)
    for i, bar in enumerate(bars2):
        width = bar.get_width()
        ax2.text(width + 0.02, bar.get_y() + bar.get_height()/2,
                f'{width:.3f}', va='center', fontsize=9)
    
    plt.tight_layout()
    filename = f"05_top_bottom_cases{suffix}.png"
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] {filename} 생성")


# ============================================================================
# 비교 시각화 (여러 실험 결과)
# ============================================================================

def plot_comparison_results(all_data: List[Dict[str, Any]], output_dir: str):
    """여러 실험 결과 비교"""
    if len(all_data) < 2:
        print("[INFO] 비교할 실험이 1개 이하라 비교 차트를 생성하지 않습니다.")
        return
    
    # 설정별 이름 생성
    labels = []
    for data in all_data:
        config = data.get('config', {})
        emb = config.get('embedding_model', '?').split('-')[-1]
        topk = config.get('top_k', '?')
        label = f"{emb}\nTop-{topk}"
        labels.append(label)
    
    # 데이터 추출
    avg_sims = [d['summary']['avg_similarity'] for d in all_data]
    median_sims = [d['summary']['median_similarity'] for d in all_data]
    threshold_70 = [d['summary']['threshold_0.7'] / d['summary']['total'] for d in all_data]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # 평균 유사도
    bars1 = axes[0].bar(labels, avg_sims, color='#4ECDC4', edgecolor='black', linewidth=1.5)
    axes[0].set_ylabel('Score', fontsize=11)
    axes[0].set_title('Average Similarity Comparison', fontsize=12, fontweight='bold')
    axes[0].set_ylim(0, 1.0)
    for bar in bars1:
        height = bar.get_height()
        axes[0].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{height:.3f}', ha='center', fontsize=10, fontweight='bold')
    
    # 중앙값
    bars2 = axes[1].bar(labels, median_sims, color='#45B7D1', edgecolor='black', linewidth=1.5)
    axes[1].set_ylabel('Score', fontsize=11)
    axes[1].set_title('Median Similarity Comparison', fontsize=12, fontweight='bold')
    axes[1].set_ylim(0, 1.0)
    for bar in bars2:
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{height:.3f}', ha='center', fontsize=10, fontweight='bold')
    
    # ≥0.7 비율
    bars3 = axes[2].bar(labels, threshold_70, color='#98D8C8', edgecolor='black', linewidth=1.5)
    axes[2].set_ylabel('Rate', fontsize=11)
    axes[2].set_title('≥0.7 Threshold Rate', fontsize=12, fontweight='bold')
    axes[2].set_ylim(0, 1.0)
    for bar in bars3:
        height = bar.get_height()
        axes[2].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{height:.1%}', ha='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '00_comparison_results.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] 00_comparison_results.png 생성")


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
    results_dir = os.path.abspath(RESULTS_DIR)
    all_data = load_result_files(results_dir)
    
    # 3. 출력 디렉토리 생성
    output_dir = os.path.abspath(OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[2] 출력 디렉토리: {output_dir}")
    
    # 4. 개별 결과 시각화
    print("\n[3] 개별 결과 시각화 중...")
    print("-" * 80)
    
    for idx, data in enumerate(all_data, 1):
        suffix = f"_{idx}" if len(all_data) > 1 else ""
        print(f"\n실험 {idx}: {data['_filename']}")
        plot_single_summary(data, output_dir, suffix)
        plot_similarity_distribution(data, output_dir, suffix)
        plot_threshold_comparison(data, output_dir, suffix)
        plot_performance_trend(data, output_dir, suffix)
        plot_top_bottom_cases(data, output_dir, suffix)
    
    # 5. 비교 시각화 (여러 실험이 있을 경우)
    if len(all_data) > 1:
        print("\n[4] 비교 결과 시각화 중...")
        print("-" * 80)
        plot_comparison_results(all_data, output_dir)
    
    print("-" * 80)
    print(f"\n[OK] 시각화 완료!")
    print(f"\n저장 위치: {output_dir}")
    print(f"\n생성된 파일 ({5 * len(all_data) + (1 if len(all_data) > 1 else 0)}개):")
    print("  - 00_comparison_results.png     : 실험 비교 (여러 개일 경우)")
    for i in range(1, len(all_data) + 1):
        suffix = f"_{i}" if len(all_data) > 1 else ""
        print(f"\n  실험 {i}:")
        print(f"    - 01_summary_table{suffix}.png             : 요약 테이블")
        print(f"    - 02_similarity_distribution{suffix}.png   : 유사도 분포")
        print(f"    - 03_threshold_comparison{suffix}.png      : 임계값 비교")
        print(f"    - 04_performance_trend{suffix}.png         : 성능 추이")
        print(f"    - 05_top_bottom_cases{suffix}.png          : 상위/하위 사례")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
