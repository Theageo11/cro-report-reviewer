import os
from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from datetime import datetime
from lxml import etree
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
import re

def get_or_create_comments_part(doc):
    """
    Ensure the document has a comments part in a safe way.
    """
    main_doc_part = doc.part
    
    # Check if the part already exists in the package to avoid duplicates
    for part in main_doc_part.package.parts:
        if part.partname == '/word/comments.xml':
            return part, parse_xml(part.blob)

    # If not found, create it
    from docx.opc.constants import CONTENT_TYPE as CT
    from docx.opc.packuri import PackURI
    from docx.opc.part import Part
    
    comments_xml_str = '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"></w:comments>'
    comments_part = Part(
        PackURI('/word/comments.xml'),
        CT.WML_COMMENTS,
        comments_xml_str.encode('utf-8'),
        main_doc_part.package
    )
    rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    main_doc_part.relate_to(comments_part, rel_type)
    return comments_part, parse_xml(comments_xml_str)

def add_native_comment(doc, element_id, text, original_text=None, author='Agent', initials='AG'):
    """
    Add a native Word comment to a paragraph, table cell, or image run.
    Prioritizes original_text for positioning.
    """
    comments_part, comments_xml = get_or_create_comments_part(doc)
    
    # 1. Create the comment element
    comment_id = str(len(comments_xml.findall(qn('w:comment'))))
    comment = OxmlElement('w:comment')
    comment.set(qn('w:id'), comment_id)
    comment.set(qn('w:author'), author)
    comment.set(qn('w:initials'), initials)
    comment.set(qn('w:date'), datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'))
    
    cp = OxmlElement('w:p')
    cr = OxmlElement('w:r')
    # Handle multi-line text in comments
    lines = text.split('\n')
    for i, line in enumerate(lines):
        ct = OxmlElement('w:t')
        ct.text = line
        cr.append(ct)
        if i < len(lines) - 1:
            cr.append(OxmlElement('w:br'))
            
    cp.append(cr)
    comment.append(cp)
    comments_xml.append(comment)
    
    # Update the part's blob
    comments_part._blob = etree.tostring(comments_xml, encoding='utf-8', xml_declaration=False)

    # 2. Find the target element
    target_node = None
    
    def get_text(el):
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text_nodes = el.findall('.//w:t', ns)
        return ''.join([node.text for node in text_nodes if node.text])

    # Strategy A: Search by original_text (more accurate for user)
    if original_text and original_text.strip():
        # Clean up search text: remove all whitespace for robust matching
        def clean_all_ws(t):
            return "".join(t.split())
            
        # Try full text first, then line by line if it's multi-line
        search_lines = [line.strip() for line in original_text.split('\n') if line.strip()]
        
        for el in doc.element.body:
            if isinstance(el, (CT_P, CT_Tbl)):
                el_text_raw = get_text(el)
                el_text_clean = clean_all_ws(el_text_raw)
                
                found = False
                # Try matching the first significant line of original_text
                if search_lines:
                    first_line_clean = clean_all_ws(search_lines[0])
                    if len(first_line_clean) > 2 and first_line_clean in el_text_clean:
                        found = True
                
                if found:
                    if isinstance(el, CT_P):
                        target_node = el
                    else:
                        # For tables, find the paragraph containing the text
                        ps = el.xpath('.//w:p')
                        for p in ps:
                            if clean_all_ws(search_lines[0]) in clean_all_ws(get_text(p)):
                                target_node = p
                                break
                        if not target_node and ps:
                            target_node = ps[0]
                    if target_node is not None:
                        break

    # Strategy B: Fallback to element_id if Strategy A failed
    if target_node is None:
        curr_id = 0
        for el in doc.element.body:
            if isinstance(el, CT_P):
                p = Paragraph(el, doc)
                found_in_p = False
                for run in p.runs:
                    if 'drawing' in run.element.xml:
                        # Match parser.py logic: count each embedded image
                        embeds = re.findall(r'r:embed="([^"]+)"', run.element.xml)
                        for _ in embeds:
                            if curr_id == element_id:
                                target_node = run.element
                                found_in_p = True
                                break
                            curr_id += 1
                        if found_in_p: break
                
                if found_in_p: break
                
                p_text = get_text(el).strip()
                if p_text:
                    if curr_id == element_id:
                        target_node = el
                        break
                    curr_id += 1
            elif isinstance(el, CT_Tbl):
                if curr_id == element_id:
                    paragraphs = el.xpath('.//w:p')
                    target_node = paragraphs[0] if paragraphs else el
                    break
                curr_id += 1
            
    if target_node is not None:
        # 3. Insert comment references
        if isinstance(target_node, CT_P):
            # Inside paragraph
            comment_range_start = OxmlElement('w:commentRangeStart')
            comment_range_start.set(qn('w:id'), comment_id)
            pPr = target_node.find(qn('w:pPr'))
            if pPr is not None:
                pPr.addnext(comment_range_start)
            else:
                target_node.insert(0, comment_range_start)
            
            comment_range_end = OxmlElement('w:commentRangeEnd')
            comment_range_end.set(qn('w:id'), comment_id)
            target_node.append(comment_range_end)
            
            r_ref = OxmlElement('w:r')
            comment_ref = OxmlElement('w:commentReference')
            comment_ref.set(qn('w:id'), comment_id)
            r_ref.append(comment_ref)
            target_node.append(r_ref)
        else:
            # It's a run (for image) or a table (fallback)
            comment_range_start = OxmlElement('w:commentRangeStart')
            comment_range_start.set(qn('w:id'), comment_id)
            target_node.addprevious(comment_range_start)

            comment_range_end = OxmlElement('w:commentRangeEnd')
            comment_range_end.set(qn('w:id'), comment_id)
            target_node.addnext(comment_range_end)

            r_ref = OxmlElement('w:r')
            comment_ref = OxmlElement('w:commentReference')
            comment_ref.set(qn('w:id'), comment_id)
            r_ref.append(comment_ref)
            comment_range_end.addnext(r_ref)

def generate_commented_docx(original_path, output_path, selected_issues):
    """
    Generate a new DOCX with native comments for selected issues.
    """
    doc = Document(original_path)
    
    for issue in selected_issues:
        try:
            eid = int(issue.get('element_id', -1))
            original_text = issue.get('original_text', '')
            
            issue_type = issue.get('issue_type', 'Issue')
            description = issue.get('description', '')
            suggestion = issue.get('suggestion', '')
            
            text = f"[{issue_type}] {description}\n建议: {suggestion}"
            add_native_comment(doc, eid, text, original_text=original_text)
        except (ValueError, KeyError):
            continue
            
    doc.save(output_path)
