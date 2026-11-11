"""백엔드(Model) 패키지. PyQt를 import하지 않는다 (export.py만 예외)."""

from umlparser.class_parser import parse

__all__ = ["parse"]
