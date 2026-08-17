import importlib
import pkgutil
from typing import Optional

from app.parsers.base import BaseParser

_parsers: list[BaseParser] = []


def _discover_parsers():
    import app.parsers as parsers_pkg

    for _, module_name, _ in pkgutil.iter_modules(parsers_pkg.__path__):
        if module_name in ("base", "registry"):
            continue
        module = importlib.import_module(f"app.parsers.{module_name}")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseParser)
                and attr is not BaseParser
            ):
                _parsers.append(attr())


def get_all_parsers() -> list[BaseParser]:
    if not _parsers:
        _discover_parsers()
    return _parsers


def get_parser_for_url(url: str) -> Optional[BaseParser]:
    for parser in get_all_parsers():
        if parser.detect(url):
            return parser
    return None
