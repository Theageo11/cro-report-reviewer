import os
import re
from typing import List, Dict, Union, Any
import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
import mammoth
import io

class DocxParser:
    def __init__(self, temp_image_dir: str = "temp_images"):
        self.temp_image_dir = temp_image_dir
        if not os.path.exists(temp_image_dir):
            os.makedirs(temp_image_dir)

    def get_content_and_html(self, file_path: str) -> Dict[str, Any]:
        """
        Parse DOCX and return both structured content and tagged HTML.
        Uses a robust sibling-tagging strategy to avoid breaking Word fields.
        """
        from bs4 import BeautifulSoup
        
        # 1. Extract clean content for LLM using a fresh doc object
        doc = docx.Document(file_path)
        content_list = []
        element_id = 0
        for element in doc.element.body:
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, doc)
                images = self._extract_images_from_paragraph(paragraph, doc)
                for img_path in images:
                    content_list.append({"id": element_id, "type": "image", "path": img_path})
                    element_id += 1
                text = paragraph.text.strip()
                if text:
                    content_list.append({"id": element_id, "type": "text", "content": text})
                    element_id += 1
            elif isinstance(element, CT_Tbl):
                table = Table(element, doc)
                table_data = self._extract_table_data(table)
                content_list.append({"id": element_id, "type": "table", "content": table_data})
                element_id += 1

        # 2. Create a marked version for HTML conversion
        # We insert marker paragraphs BEFORE each target element
        marked_doc = docx.Document(file_path)
        element_id = 0
        body_elements = list(marked_doc.element.body)
        for element in body_elements:
            target_id = None
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, marked_doc)
                images = self._extract_images_from_paragraph(paragraph, marked_doc)
                element_id += len(images)
                if paragraph.text.strip():
                    target_id = element_id
                    element_id += 1
            elif isinstance(element, CT_Tbl):
                target_id = element_id
                element_id += 1
            
            if target_id is not None:
                # Insert a marker paragraph before this element
                new_p = marked_doc.add_paragraph(f"MARKER_ID_{target_id}")
                element.addprevious(new_p._p)

        # 3. Convert to HTML
        doc_buffer = io.BytesIO()
        marked_doc.save(doc_buffer)
        doc_buffer.seek(0)
        html_res = mammoth.convert_to_html(doc_buffer)
        soup = BeautifulSoup(html_res.value, 'html.parser')

        # 4. Post-process HTML: find markers and tag siblings
        for marker_p in soup.find_all('p', string=re.compile(r'MARKER_ID_\d+')):
            m = re.search(r'MARKER_ID_(\d+)', marker_p.get_text())
            if m:
                eid = m.group(1)
                # The actual element is the next sibling
                sibling = marker_p.find_next_sibling()
                if sibling:
                    sibling['id'] = f"doc-el-{eid}"
                marker_p.decompose() # Remove the marker

        return {
            "content": content_list,
            "html": str(soup)
        }

    def _extract_images_from_paragraph(self, paragraph: Paragraph, doc: Document) -> List[str]:
        images = []
        for run in paragraph.runs:
            if 'drawing' in run.element.xml:
                xml = run.element.xml
                embeds = re.findall(r'r:embed="([^"]+)"', xml)
                for embed_id in embeds:
                    if embed_id in doc.part.rels:
                        rel = doc.part.rels[embed_id]
                        if "image" in rel.target_ref:
                            image_part = rel.target_part
                            image_data = image_part.blob
                            filename = f"img_{len(os.listdir(self.temp_image_dir))}.png"
                            filepath = os.path.join(self.temp_image_dir, filename)
                            with open(filepath, "wb") as f:
                                f.write(image_data)
                            images.append(filepath)
        return images

    def _extract_table_data(self, table: Table) -> str:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")
        return "\n".join(rows)
