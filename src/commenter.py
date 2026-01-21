import os
from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from datetime import datetime

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

def add_native_comment(doc, element_id, text, author='Agent', initials='AG'):
    """
    Add a native Word comment to a paragraph or table cell.
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
    ct = OxmlElement('w:t')
    ct.text = text
    cr.append(ct)
    cp.append(cr)
    comment.append(cp)
    comments_xml.append(comment)
    
    # Update the part's blob
    comments_part._blob = comments_xml.xml.encode('utf-8')

    # 2. Find the target element
    target_element = None
    curr_id = 0
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    
    for el in doc.element.body:
        if isinstance(el, CT_P):
            # Match parser.py logic
            has_image = 'drawing' in el.xml
            if has_image:
                if curr_id == element_id:
                    target_element = el
                    break
                curr_id += 1
            
            if el.xpath('w:t'):
                if curr_id == element_id:
                    target_element = el
                    break
                curr_id += 1
        elif isinstance(el, CT_Tbl):
            if curr_id == element_id:
                target_element = el
                break
            curr_id += 1
            
    if target_element is not None:
        if isinstance(target_element, CT_Tbl):
            try:
                target_element = target_element.xpath('.//w:p')[0]
            except IndexError:
                return

        # 3. Insert comment references
        comment_range_start = OxmlElement('w:commentRangeStart')
        comment_range_start.set(qn('w:id'), comment_id)
        target_element.insert(0, comment_range_start)

        comment_range_end = OxmlElement('w:commentRangeEnd')
        comment_range_end.set(qn('w:id'), comment_id)
        target_element.append(comment_range_end)

        r_ref = OxmlElement('w:r')
        comment_ref = OxmlElement('w:commentReference')
        comment_ref.set(qn('w:id'), comment_id)
        r_ref.append(comment_ref)
        target_element.append(r_ref)

def generate_commented_docx(original_path, output_path, selected_issues):
    """
    Generate a new DOCX with native comments for selected issues.
    """
    doc = Document(original_path)
    
    for issue in selected_issues:
        try:
            eid = int(issue['element_id'])
            text = f"[{issue['issue_type']}] {issue['description']}\n建议: {issue['suggestion']}"
            add_native_comment(doc, eid, text)
        except (ValueError, KeyError):
            continue
            
    doc.save(output_path)
