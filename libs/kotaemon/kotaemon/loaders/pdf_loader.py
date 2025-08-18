import base64
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional
import logging

from decouple import config
from fsspec import AbstractFileSystem
from llama_index.readers.file import PDFReader
from PIL import Image

from kotaemon.base import Document
from kotaemon.loaders.openai_vision_image_reader import OpenAIVisionImageReader
import tempfile
import os

PDF_LOADER_DPI = config("PDF_LOADER_DPI", default=40, cast=int)


def get_page_thumbnails(
    file_path: Path, pages: list[int], dpi: int = PDF_LOADER_DPI
) -> List[Image.Image]:
    """Get image thumbnails of the pages in the PDF file.

    Args:
        file_path (Path): path to the image file
        page_number (list[int]): list of page numbers to extract

    Returns:
        list[Image.Image]: list of page thumbnails
    """

    img: Image.Image
    suffix = file_path.suffix.lower()
    assert suffix == ".pdf", "This function only supports PDF files."
    try:
        import fitz
    except ImportError:
        raise ImportError("Please install PyMuPDF: 'pip install PyMuPDF'")

    doc = fitz.open(file_path)

    output_imgs = []
    for page_number in pages:
        page = doc.load_page(page_number)
        pm = page.get_pixmap(dpi=dpi, alpha=False)  # Ensure no alpha channel
        img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
        output_imgs.append(convert_image_to_base64(img))

    return output_imgs


def convert_image_to_base64(img: Image.Image) -> str:
    # convert the image into base64
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
    img_base64 = f"data:image/png;base64,{img_base64}"

    return img_base64


class PDFThumbnailReader(PDFReader):
    """PDF parser with thumbnail for each page."""

    def __init__(self) -> None:
        """
        Initialize PDFReader.
        """
        super().__init__(return_full_document=False)

    def load_data(
        self,
        file: Path,
        extra_info: Optional[Dict] = None,
        fs: Optional[AbstractFileSystem] = None,
    ) -> List[Document]:
        """Parse file."""
        documents = super().load_data(file, extra_info, fs)

        page_numbers_str = []
        filtered_docs = []
        is_int_page_number: dict[str, bool] = {}

        for doc in documents:
            if "page_label" in doc.metadata:
                page_num_str = doc.metadata["page_label"]
                page_numbers_str.append(page_num_str)
                try:
                    _ = int(page_num_str)
                    is_int_page_number[page_num_str] = True
                    filtered_docs.append(doc)
                except ValueError:
                    is_int_page_number[page_num_str] = False
                    continue

        documents = filtered_docs
        page_numbers = list(range(len(page_numbers_str)))

        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.info(f"Page numbers: {len(page_numbers)}")
        logger.info(f"page_numbers: {page_numbers}")
        logger.info(f"page_numbers_str: {page_numbers_str}")
        # Only use OpenAI Vision for actual images in the PDF, not for text-only pages
        vision_reader = OpenAIVisionImageReader()
        try:
            import fitz
        except ImportError:
            raise ImportError("Please install PyMuPDF: 'pip install PyMuPDF'")

        # Generate page-level thumbnails for all pages
        page_thumbnails = get_page_thumbnails(file, page_numbers)
        logger.info(f"Number of page_thumbnails: {len(page_thumbnails)}")

        pdf_doc = fitz.open(file)
        for idx, page_number in enumerate(page_numbers):
            page = pdf_doc.load_page(page_number)
            images = page.get_images(full=True)
            page_thumbnail_b64 = page_thumbnails[idx] if idx < len(page_thumbnails) else None

            # Always check for vector drawings (diagrams, flowcharts, etc.)
            drawings = page.get_drawings()
            if drawings and page_thumbnail_b64 and len(drawings) > 100:
                logger.info(f'Extracting diagram/flowchart description for page {page_number}...')
                # Save thumbnail to temp file
                img_data = page_thumbnail_b64.split(",")[1]
                img_bytes = base64.b64decode(img_data)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                    tmp_img.write(img_bytes)
                    tmp_img_path = tmp_img.name
                try:
                    vision_docs = vision_reader.load_data(Path(tmp_img_path))
                    description = vision_docs[0].text if vision_docs else ""
                except Exception:
                    description = ""
                finally:
                    os.remove(tmp_img_path)
                # Append vision description to the existing document for this page
                if idx < len(documents):
                    doc = documents[idx]
                    doc.text = f"{doc.text}\n\n[Diagram/Flowchart Description]\n{description}"
                    doc.metadata["has_page_thumbnail"] = True
                else:
                    # Fallback: create a new Document if mapping fails
                    documents.append(
                        Document(
                            text=description,
                            metadata={
                                "has_page_thumbnail": True,
                                "type": "page_diagram",
                                "page_label": page_numbers_str[idx],
                                **(extra_info if extra_info is not None else {}),
                            },
                        )
                    )

            for img_index, img in enumerate(images):
                xref = img[0]
                base_image = pdf_doc.extract_image(xref)
                width = base_image.get("width")
                height = base_image.get("height")
                smask = base_image.get("smask")
                img_ext = base_image["ext"]
                img_bytes = base_image["image"]
                # Only process if not a soft mask and has reasonable size
                if smask is not None or not width or not height or width < 200 or height < 200:
                    continue  # Skip soft masks, small, or invalid images
                # Save image to temp file
                with tempfile.NamedTemporaryFile(suffix=f".{img_ext}", delete=False) as tmp_img:
                    tmp_img.write(img_bytes)
                    tmp_img_path = tmp_img.name
                # Convert to base64 for metadata
                img_base64 = f"data:image/{img_ext};base64," + base64.b64encode(img_bytes).decode("utf-8")
                logger.info(f'Extracting image description for page {page_number}, image {img_index}...')
                try:
                    vision_docs = vision_reader.load_data(Path(tmp_img_path))
                    description = vision_docs[0].text if vision_docs else ""
                except Exception:
                    description = ""
                finally:
                    os.remove(tmp_img_path)
                # Append vision description to the existing document for this page
                if idx < len(documents):
                    doc = documents[idx]
                    doc.text = f"{doc.text}\n\n[Image Description {img_index+1}]\n{description}"
                    # Optionally, store all image origins in a list in metadata
                    if "num_images" not in doc.metadata:
                        doc.metadata["num_images"] = 0
                    doc.metadata["num_images"] += 1
                    doc.metadata["has_page_thumbnail"] = True
                else:
                    # Fallback: create a new Document if mapping fails
                    documents.append(
                        Document(
                            text=description,
                            metadata={
                                "has_page_thumbnail": True,
                                "type": "image",
                                "page_label": page_numbers_str[idx],
                                "image_index": img_index,
                                **(extra_info if extra_info is not None else {}),
                            },
                        )
                    )
        documents.extend(
            [ 
                Document(
                    text="Page thumbnail",
                    metadata={
                        "image_origin": page_thumbnail,
                        "type": "thumbnail",
                        "page_label": page_number,
                        **(extra_info if extra_info is not None else {}),
                    },
                )
                for (page_thumbnail, page_number) in zip(
                    page_thumbnails, page_numbers_str
                )
                if is_int_page_number[page_number]
            ]
        )


        return documents

