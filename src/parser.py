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
        Uses a marker injection strategy for 100% reliable localization.
        """
        # 1. Extract content for LLM using the original document
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

        # 2. Create a marked copy for HTML conversion
        # We insert markers like [[REF_n]] into the text
        marked_doc = docx.Document(file_path)
        m_element_id = 0
        for element in marked_doc.element.body:
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, marked_doc)
                images = self._extract_images_from_paragraph(paragraph, marked_doc)
                m_element_id += len(images)
                
                if paragraph.text.strip():
                    # Prepend marker to the first run
                    if paragraph.runs:
                        paragraph.runs[0].text = f"[[REF_{m_element_id}]]" + paragraph.runs[0].text
                    else:
                        paragraph.add_run(f"[[REF_{m_element_id}]]")
                    m_element_id += 1
            elif isinstance(element, CT_Tbl):
                table = Table(element, marked_doc)
                # Insert marker in the first cell
                if table.rows and table.rows[0].cells:
                    cell = table.rows[0].cells[0]
                    if cell.paragraphs:
                        p = cell.paragraphs[0]
                        if p.runs:
                            p.runs[0].text = f"[[REF_{m_element_id}]]" + p.runs[0].text
                        else:
                            p.add_run(f"[[REF_{m_element_id}]]")
                m_element_id += 1

        # 3. Convert marked doc to HTML
        doc_buffer = io.BytesIO()
        marked_doc.save(doc_buffer)
        doc_buffer.seek(0)
        html_res = mammoth.convert_to_html(doc_buffer)
        html_val = html_res.value

        # 4. Replace markers with tagged spans for UI localization
        tagged_html = re.sub(
            r'\[\[REF_(\d+)\]\]', 
            r'<span id="doc-el-\1" class="doc-anchor"></span>', 
            html_val
        )

        return {
            "content": content_list,
            "html": tagged_html
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
