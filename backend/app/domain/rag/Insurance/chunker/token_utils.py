from typing import List
import tiktoken

from .config import MODEL_NAME

_enc = tiktoken.get_encoding("cl100k_base")


def get_num_tokens(text: str) -> int:
    # use cl100k_base directly to avoid network
    return len(_enc.encode(text))


def tokenize(text: str) -> List[int]:
    return _enc.encode(text)


def detokenize(tokens: List[int]) -> str:
    return _enc.decode(tokens)