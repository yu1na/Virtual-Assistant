"""Main orchestrator for Insurance PDF Extractor (modular)."""
from pathlib import Path
from typing import List, Dict

import fitz
import pdfplumber

from .page_processor import process_page
from .file_manager import resolve_input_pdfs, resolve_output_path, save_json
from .utils import get_logger

logger = get_logger(__name__)


class PDFExtractor:
	def extract_all(self, api_key: str | None = None) -> List[Path]:
		outputs: List[Path] = []
		pdfs = resolve_input_pdfs()
		if not pdfs:
			logger.info("No PDFs found in documents/ (or proceeds/).")
			return outputs
		for pdf in pdfs:
			out = self.extract(str(pdf), api_key=api_key)
			outputs.append(out)
		return outputs

	def extract(self, pdf_path: str, api_key: str | None = None) -> Path:
		pdf_path_obj = Path(pdf_path)
		if not pdf_path_obj.exists():
			raise FileNotFoundError(f"PDF not found: {pdf_path_obj}")
		logger.info(f"Starting extraction: {pdf_path_obj.name}")

		results: List[Dict] = []
		with fitz.open(pdf_path_obj) as doc, pdfplumber.open(pdf_path_obj) as plumber:
			total_pages = len(doc)
			for page_index in range(total_pages):
				pymupdf_page = doc[page_index]
				plumber_page = plumber.pages[page_index]
				page_dict = process_page(pymupdf_page, plumber_page, api_key)
				page_dict["page"] = page_index + 1
				results.append(page_dict)
				# Visual progress for each page
				try:
					print(f"[Extractor] {pdf_path_obj.name} page {page_index+1}/{total_pages}")
				except Exception:
					pass

		output_path = resolve_output_path(pdf_path_obj.name)
		payload = {
			"file": str(pdf_path_obj),
			"total_pages": len(results),
			"pages": results,
		}
		save_json(output_path, payload)
		logger.info(f"Completed: {output_path} ({len(results)} pages)")
		return output_path


__all__ = ["PDFExtractor"]


if __name__ == "__main__":
	"""CLI entry for visual progress while extracting all PDFs."""
	import sys
	from time import sleep

	# Ensure backend is on PYTHONPATH if run via -m
	try:
		# Basic progress printout
		print("[Extractor] Scanning documents/proceeds for PDFs...")
		extractor = PDFExtractor()
		outputs = []
		pdfs = resolve_input_pdfs()
		if not pdfs:
			print("[Extractor] No PDFs found. Place files in documents/.")
			sys.exit(0)
		total = len(pdfs)
		for idx, pdf in enumerate(pdfs, start=1):
			print(f"[Extractor] ({idx}/{total}) Processing: {pdf.name}")
			out = extractor.extract(str(pdf))
			print(f"[Extractor] -> Saved: {out}")
			outputs.append(out)
			# small pause to make progress visually distinct
			sleep(0.05)
		print(f"[Extractor] Done. {len(outputs)} files extracted.")
	except KeyboardInterrupt:
		print("[Extractor] Interrupted by user.")
		sys.exit(130)
