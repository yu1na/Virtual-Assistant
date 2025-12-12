"""
RAG 시스템 CLI 인터페이스

PDF 업로드, 문서 처리, 질의응답을 터미널에서 실행할 수 있습니다.
"""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import rag_config
from .pdf_processor import PDFProcessor
from .document_converter import DocumentConverter
from .vector_store import VectorStore
from .retriever import RAGRetriever
from .schemas import QueryRequest
from .utils import get_logger

logger = get_logger(__name__)

console = Console()


class RAGCLI:
    """RAG CLI 인터페이스"""
    
    def __init__(self):
        self.config = rag_config
        self.pdf_processor = PDFProcessor()
        self.document_converter = DocumentConverter()
        self.vector_store = VectorStore()
        self.retriever = RAGRetriever()
    
    def upload_pdf(self, input_path: str):
        """
        파일 또는 폴더를 업로드하고 처리
        
        Args:
            input_path: 파일 경로 또는 폴더 경로
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            console.print(f"[red]오류: 경로를 찾을 수 없습니다: {input_path}[/red]")
            return
        
        # 폴더인지 파일인지 판단
        if input_path.is_dir():
            # 폴더인 경우: 내부 모든 파일 처리
            self._process_directory(input_path)
        else:
            # 파일인 경우: 단일 파일 처리
            self._process_single_file(input_path)
    
    def _process_directory(self, directory: Path):
        """폴더 내 모든 파일 처리"""
        # 지원하는 파일 확장자
        supported_extensions = {'.pdf', '.txt', '.md'}
        
        # 폴더 내 모든 파일 찾기
        files = [
            f for f in directory.iterdir() 
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]
        
        if not files:
            console.print(f"[yellow]경고: 처리할 수 있는 파일이 없습니다: {directory}[/yellow]")
            console.print(f"[dim]지원 확장자: {', '.join(supported_extensions)}[/dim]")
            return
        
        console.print(Panel.fit(
            f"[bold cyan]폴더 처리 시작[/bold cyan]\n"
            f"폴더: {directory.name}\n"
            f"파일 수: {len(files)}개",
            border_style="cyan"
        ))
        
        success_count = 0
        error_count = 0
        
        for idx, file_path in enumerate(files, 1):
            console.print(f"\n[dim][{idx}/{len(files)}] 처리 중: {file_path.name}[/dim]")
            try:
                self._process_single_file(file_path, show_header=False)
                success_count += 1
            except Exception as e:
                console.print(f"[red]  ✗ 오류: {file_path.name} - {e}[/red]")
                error_count += 1
                logger.exception(f"파일 처리 중 오류: {file_path}")
        
        # 전체 결과 출력
        console.print("\n" + "="*60)
        result_table = Table(title="폴더 처리 결과", show_header=True, header_style="bold magenta")
        result_table.add_column("항목", style="cyan")
        result_table.add_column("값", style="green")
        
        result_table.add_row("총 파일 수", str(len(files)))
        result_table.add_row("성공", f"[green]{success_count}개[/green]")
        result_table.add_row("실패", f"[red]{error_count}개[/red]" if error_count > 0 else "0개")
        
        console.print(result_table)
        console.print(f"\n[green]✓ 폴더 처리 완료![/green]")
    
    def _process_single_file(self, file_path: Path, show_header: bool = True):
        """
        단일 파일 처리
        
        Args:
            file_path: 파일 경로
            show_header: 헤더 출력 여부
        """
        # 파일 확장자 확인
        extension = file_path.suffix.lower()
        
        if show_header:
            file_type = "PDF 문서" if extension == '.pdf' else "텍스트 문서"
            console.print(Panel.fit(
                f"[bold cyan]{file_type} 처리 시작[/bold cyan]\n파일: {file_path.name}",
                border_style="cyan"
            ))
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # 1. 파일 처리 (확장자에 따라 분기)
                if extension == '.pdf':
                    task1 = progress.add_task("[cyan]PDF 파싱 중...", total=None)
                    processed_doc = self.pdf_processor.process_pdf(str(file_path))
                elif extension in {'.txt', '.md'}:
                    task1 = progress.add_task("[cyan]텍스트 파일 읽는 중...", total=None)
                    processed_doc = self.pdf_processor.process_text(str(file_path))
                else:
                    raise ValueError(f"지원하지 않는 파일 형식입니다: {extension}")
                
                progress.update(task1, completed=True)
                
                # 2. 청킹
                task2 = progress.add_task("[cyan]문서 청킹 중...", total=None)
                chunks = self.document_converter.create_chunks(processed_doc)
                progress.update(task2, completed=True)
                
                # 3. 임베딩 및 저장
                task3 = progress.add_task("[cyan]임베딩 생성 및 저장 중...", total=None)
                added_count = self.vector_store.add_document(processed_doc, chunks)
                progress.update(task3, completed=True)
                
                # 4. 임베딩을 포함한 JSON 저장
                task4 = progress.add_task("[cyan]JSON 파일 저장 중...", total=None)
                self.pdf_processor.save_chunks_with_embeddings(processed_doc, chunks)
                progress.update(task4, completed=True)
            
            # 결과 출력
            if show_header:
                result_table = Table(title="처리 결과", show_header=True, header_style="bold magenta")
                result_table.add_column("항목", style="cyan")
                result_table.add_column("값", style="green")
                
                result_table.add_row("파일명", processed_doc.filename)
                result_table.add_row("총 페이지", str(processed_doc.total_pages))
                result_table.add_row("추출된 컨텐츠", str(len(processed_doc.contents)))
                result_table.add_row("생성된 청크", str(len(chunks)))
                result_table.add_row("저장된 청크", str(added_count))
                
                console.print(result_table)
                console.print(f"\n[green]✓ 문서 처리 완료![/green]")
            else:
                console.print(f"  [green]✓ {file_path.name} 처리 완료 ({len(chunks)}개 청크)[/green]")
            
        except Exception as e:
            logger.exception(f"파일 처리 중 오류: {file_path}")
            if show_header:
                console.print(f"[red]오류 발생: {e}[/red]")
            raise  # 폴더 처리 시 상위로 전파
    
    def query_interactive(self):
        """대화형 질의응답 모드"""
        console.print(Panel.fit(
            "[bold cyan]RAG 질의응답 시스템[/bold cyan]\n"
            "질문을 입력하세요. 종료하려면 'exit' 또는 'quit'를 입력하세요.",
            border_style="cyan"
        ))
        
        # 저장된 문서 수 확인
        doc_count = self.vector_store.count_documents()
        console.print(f"[dim]저장된 문서 청크: {doc_count}개[/dim]\n")
        
        if doc_count == 0:
            console.print("[yellow]경고: 저장된 문서가 없습니다. 먼저 PDF를 업로드하세요.[/yellow]")
            return
        
        while True:
            try:
                # 질문 입력
                query = console.input("\n[bold green]질문>[/bold green] ")
                
                if query.lower() in ['exit', 'quit', '종료']:
                    console.print("[cyan]질의응답을 종료합니다.[/cyan]")
                    break
                
                if not query.strip():
                    continue
                
                # 질의응답 처리
                with console.status("[cyan]답변 생성 중...[/cyan]"):
                    request = QueryRequest(query=query, top_k=self.config.RAG_TOP_K)
                    response = self.retriever.query(request)
                
                # 답변 출력
                console.print("\n" + "="*80)
                console.print(Panel(
                    Markdown(response.answer),
                    title="[bold cyan]답변[/bold cyan]",
                    border_style="cyan"
                ))
                
                # 참고 문서 출력
                if response.retrieved_chunks:
                    console.print(f"\n[bold cyan]참고 문서 ({len(response.retrieved_chunks)}개):[/bold cyan]")
                    for i, chunk in enumerate(response.retrieved_chunks, 1):
                        score_color = "green" if chunk.score >= 0.7 else "yellow" if chunk.score >= 0.5 else "red"
                        console.print(
                            f"  {i}. [cyan]{chunk.metadata.get('filename', 'Unknown')}[/cyan] "
                            f"(페이지 {chunk.metadata.get('page_number', '?')}) "
                            f"- 유사도: [{score_color}]{chunk.score:.4f}[/{score_color}]"
                        )
                
                console.print(f"\n[dim]처리 시간: {response.processing_time:.2f}초[/dim]")
                console.print("="*80)
                
            except KeyboardInterrupt:
                console.print("\n[cyan]질의응답을 종료합니다.[/cyan]")
                break
            except Exception as e:
                console.print(f"[red]오류 발생: {e}[/red]")
                logger.exception("질의응답 중 오류")
    
    def query_single(self, query: str, top_k: int = None):
        """단일 질문 처리"""
        if top_k is None:
            top_k = self.config.RAG_TOP_K
        
        try:
            console.print(f"[cyan]질문:[/cyan] {query}\n")
            
            with console.status("[cyan]답변 생성 중...[/cyan]"):
                request = QueryRequest(query=query, top_k=top_k)
                response = self.retriever.query(request)
            
            # 답변 출력
            console.print(Panel(
                Markdown(response.answer),
                title="[bold cyan]답변[/bold cyan]",
                border_style="cyan"
            ))
            
            # 참고 문서
            if response.retrieved_chunks:
                console.print(f"\n[bold cyan]참고 문서 ({len(response.retrieved_chunks)}개):[/bold cyan]")
                for i, chunk in enumerate(response.retrieved_chunks, 1):
                    score_color = "green" if chunk.score >= 0.7 else "yellow" if chunk.score >= 0.5 else "red"
                    console.print(
                        f"  {i}. [cyan]{chunk.metadata.get('filename', 'Unknown')}[/cyan] "
                        f"(페이지 {chunk.metadata.get('page_number', '?')}) "
                        f"- 유사도: [{score_color}]{chunk.score:.4f}[/{score_color}]"
                    )
            
            console.print(f"\n[dim]처리 시간: {response.processing_time:.2f}초[/dim]")
            
        except Exception as e:
            console.print(f"[red]오류 발생: {e}[/red]")
            logger.exception("질의응답 중 오류")
    
    def show_stats(self):
        """저장된 문서 통계 출력"""
        doc_count = self.vector_store.count_documents()
        
        stats_table = Table(title="RAG 시스템 통계", show_header=True, header_style="bold magenta")
        stats_table.add_column("항목", style="cyan")
        stats_table.add_column("값", style="green")
        
        stats_table.add_row("저장된 청크 수", str(doc_count))
        stats_table.add_row("컬렉션 이름", self.config.CHROMA_COLLECTION_NAME)
        stats_table.add_row("임베딩 모델", self.config.EMBEDDING_MODEL)
        stats_table.add_row("번역 모델", self.config.TRANSLATION_MODEL)
        stats_table.add_row("LLM 모델", self.config.OPENAI_MODEL)
        stats_table.add_row("Top-K", str(self.config.RAG_TOP_K))
        stats_table.add_row("동적 Threshold 범위", f"{self.config.RAG_MIN_SIMILARITY_THRESHOLD} ~ {self.config.RAG_MAX_SIMILARITY_THRESHOLD}")
        
        console.print(stats_table)
    
    def update_json_paths(self):
        """기존 JSON 파일들의 file_path를 data에서 internal_docs로 업데이트"""
        console.print(Panel.fit(
            "[bold cyan]JSON 파일 경로 업데이트[/bold cyan]\n"
            "기존 처리된 JSON 파일들의 file_path를 업데이트합니다.",
            border_style="cyan"
        ))
        
        try:
            updated_count = PDFProcessor.update_existing_json_paths(self.config.PROCESSED_DIR)
            
            if updated_count > 0:
                console.print(f"\n[green]✓ {updated_count}개 JSON 파일 업데이트 완료![/green]")
            else:
                console.print("\n[yellow]업데이트할 파일이 없습니다.[/yellow]")
                
        except Exception as e:
            console.print(f"[red]오류 발생: {e}[/red]")
            logger.exception("JSON 파일 경로 업데이트 중 오류")
    
    def reset_collection(self, confirm: bool = False):
        """
        벡터 DB 컬렉션 초기화 (모든 문서 삭제)
        
        Args:
            confirm: 확인 없이 바로 초기화 (기본값: False)
        """
        if not confirm:
            console.print(Panel.fit(
                "[bold yellow]경고: 벡터 DB 컬렉션 초기화[/bold yellow]\n\n"
                "이 작업은 모든 저장된 문서와 임베딩을 삭제합니다.\n"
                "이 작업은 되돌릴 수 없습니다!",
                border_style="yellow"
            ))
            
            # 현재 저장된 문서 수 확인
            doc_count = self.vector_store.count_documents()
            console.print(f"\n[dim]현재 저장된 청크 수: {doc_count}개[/dim]")
            
            # 확인 입력
            response = console.input("\n[bold red]정말로 초기화하시겠습니까? (yes/no):[/bold red] ")
            
            if response.lower() not in ['yes', 'y', '예']:
                console.print("[cyan]초기화가 취소되었습니다.[/cyan]")
                return
        
        try:
            console.print("\n[yellow]컬렉션 초기화 중...[/yellow]")
            
            # 컬렉션 초기화
            self.vector_store.reset_collection()
            
            console.print("[green]OK - Collection reset successfully![/green]")
            console.print("[dim]You can now upload new documents.[/dim]")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logger.exception("컬렉션 초기화 중 오류")


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="RAG 문서 처리 및 질의응답 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 단일 파일 업로드
  python -m app.domain.rag.HR.cli upload document.pdf
  python -m app.domain.rag.HR.cli upload document.txt
  python -m app.domain.rag.HR.cli upload document.md
  
  # 폴더 전체 업로드 (내부 모든 PDF/TXT/MD 파일 처리)
  python -m app.domain.rag.HR.cli upload internal_docs/uploads
  
  # 대화형 질의응답
  python -m app.domain.rag.HR.cli query
  
  # 단일 질문
  python -m app.domain.rag.HR.cli query "회사의 비전은 무엇인가요?"
  
  # 통계 확인
  python -m app.domain.rag.HR.cli stats
  
  # 컬렉션 초기화 (모든 문서 삭제)
  python -m app.domain.rag.HR.cli reset
  python -m app.domain.rag.HR.cli reset --yes  # 확인 없이 바로 초기화
  
  # 기존 JSON 파일 경로 업데이트 (data → internal_docs)
  python -m app.domain.rag.HR.cli update-paths
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='명령어')
    
    # upload 명령어
    upload_parser = subparsers.add_parser('upload', help='파일 또는 폴더 업로드 및 처리')
    upload_parser.add_argument('input_path', help='PDF/TXT/MD 파일 경로 또는 폴더 경로')
    
    # query 명령어
    query_parser = subparsers.add_parser('query', help='질의응답')
    query_parser.add_argument('question', nargs='?', help='질문 (생략 시 대화형 모드)')
    query_parser.add_argument('--top-k', type=int, help='검색할 문서 수')
    
    # stats 명령어
    subparsers.add_parser('stats', help='시스템 통계 출력')
    
    # reset 명령어
    reset_parser = subparsers.add_parser('reset', help='벡터 DB 컬렉션 초기화 (모든 문서 삭제)')
    reset_parser.add_argument('--yes', '-y', action='store_true', help='확인 없이 바로 초기화')
    
    # update-paths 명령어
    subparsers.add_parser('update-paths', help='기존 JSON 파일들의 경로를 data에서 internal_docs로 업데이트')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli = RAGCLI()
    
    if args.command == 'upload':
        cli.upload_pdf(args.input_path)
    
    elif args.command == 'query':
        if args.question:
            cli.query_single(args.question, args.top_k)
        else:
            cli.query_interactive()
    
    elif args.command == 'stats':
        cli.show_stats()
    
    elif args.command == 'reset':
        cli.reset_collection(confirm=args.yes)
    
    elif args.command == 'update-paths':
        cli.update_json_paths()


if __name__ == '__main__':
    main()

