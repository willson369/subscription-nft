import re


_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def estimate_word_count(text: str) -> int:
    cjk_count = len(_CJK_PATTERN.findall(text))
    token_count = len(_TOKEN_PATTERN.findall(text))
    return cjk_count + token_count

