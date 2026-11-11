"""What the Statement import module reads: the text and tables of a document.

`read_pdf` is the production adapter. Tests build `Document`s directly, so the
rest of the module never needs a real PDF.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Page:
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass(frozen=True)
class Document:
    file_name: str
    pages: list[Page]

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)


def read_pdf(path: str | Path, file_name: str | None = None) -> Document:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        pages = [
            Page(
                text=page.extract_text() or "",
                tables=[
                    [[cell or "" for cell in row] for row in table]
                    for table in page.extract_tables()
                ],
            )
            for page in pdf.pages
        ]
    return Document(file_name or Path(path).name, pages)
