import streamlit as st
import os
import tempfile
import re
from src.parser import DocxParser
from src.llm import QwenClient
from src.commenter import generate_commented_docx
import streamlit.components.v1 as components

st.set_page_config(page_title="CRO Report Reviewer", layout="wide")

@st.cache_data
def get_doc_data(file_path):
    parser = DocxParser()
    return parser.get_content_and_html(file_path)

@st.cache_data
def get_analysis(content_items):
    llm_client = QwenClient()
    return llm_client.analyze_report(content_items)

def highlight_text(html_content, issues):
    """
    Highlight issues in the HTML content using element IDs.
    """
    if not issues:
        return html_content
        
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for i, issue in enumerate(issues):
        try:
            eid = int(issue.get("element_id", -1))
            if eid == -1: continue
            
            color = "yellow"
            if issue["issue_type"] == "Critical":
                color = "#ff4b4b"
            elif issue["issue_type"] == "Major":
                color = "#ffa500"
                
            target_tag = soup.find(id=f"doc-el-{eid}")
            if target_tag:
                target_tag['style'] = target_tag.get('style', '') + f"; background-color: {color}; border: 3px solid red; font-weight: bold; padding: 5px;"
                target_tag['id'] = f"issue-{i}" # Set ID for scrolling
        except Exception:
            continue
                
    return str(soup)

def main():
    st.title("📄 CRO 报告审核 Agent")
    st.markdown("上传 DOCX 报告，分析数据一致性、计算准确性及逻辑错误。您可以选择保留的问题并下载带的文档。")

    # File uploader
    uploaded_file = st.file_uploader("上传报告 (DOCX)", type=["docx"])

    if uploaded_file:
        # Use a persistent temp file for caching
        temp_dir = tempfile.gettempdir()
        tmp_file_path = os.path.join(temp_dir, f"uploaded_{uploaded_file.name}")
        with open(tmp_file_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        # State management
        if 'issues' not in st.session_state:
            st.session_state.issues = None
        if 'html_content' not in st.session_state:
            st.session_state.html_content = ""
        if 'parsed_content' not in st.session_state:
            st.session_state.parsed_content = []
        if 'scroll_to_id' not in st.session_state:
            st.session_state.scroll_to_id = None
        if 'selected_indices' not in st.session_state:
            st.session_state.selected_indices = []
        if 'last_uploaded' not in st.session_state or st.session_state.last_uploaded != uploaded_file.name:
            st.session_state.issues = None
            st.session_state.html_content = ""
            st.session_state.parsed_content = []
            st.session_state.scroll_to_id = None
            st.session_state.selected_indices = []
            st.session_state.last_uploaded = uploaded_file.name

        # Layout
        col1, col2 = st.columns([6, 4])

        with col1:
            st.subheader("文档预览")
            if not st.session_state.html_content:
                doc_data = get_doc_data(tmp_file_path)
                st.session_state.html_content = doc_data["html"]
                st.session_state.parsed_content = doc_data["content"]
            
            display_html = st.session_state.html_content
            if st.session_state.issues:
                display_html = highlight_text(display_html, st.session_state.issues)
            
            # Inject JavaScript for scrolling
            scroll_js = ""
            if st.session_state.scroll_to_id is not None:
                scroll_js = f"""
                <script>
                    window.onload = function() {{
                        setTimeout(function() {{
                            var element = document.getElementById('issue-{st.session_state.scroll_to_id}');
                            if (element) {{
                                element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                                element.style.outline = '5px solid red';
                                setTimeout(function() {{ element.style.outline = 'none'; }}, 2000);
                            }}
                        }}, 100);
                    }};
                </script>
                """
            
            custom_css = """
            <style>
                table { border-collapse: collapse; width: 100%; margin-bottom: 10px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                img { max-width: 400px; height: auto; display: block; margin: 10px 0; }
            </style>
            """
            
            full_preview_html = f"""
            <html>
            <head>{custom_css}</head>
            <body style="font-family: sans-serif; padding: 10px; background-color: white;">
                {scroll_js}
                {display_html}
            </body>
            </html>
            """
            components.html(full_preview_html, height=700, scrolling=True)

        with col2:
            st.subheader("分析结果")
            if st.button("🔍 开始分析", type="primary"):
                with st.spinner("正在分析文档... 请稍候"):
                    try:
                        st.session_state.issues = get_analysis(st.session_state.parsed_content)
                        st.session_state.scroll_to_id = None
                        st.session_state.selected_indices = list(range(len(st.session_state.issues)))
                    except Exception as e:
                        st.error(f"分析过程中出现错误: {str(e)}")
                        st.session_state.issues = []
                    st.rerun()
            
            if st.session_state.issues is not None:
                if not st.session_state.issues:
                    st.success("✅ 未发现严重逻辑错误或数据对齐问题！")
                else:
                    st.write(f"发现 {len(st.session_state.issues)} 个潜在问题。请勾选您想保留在文档中的批注：")
                    
                    # Issue selection and display
                    new_selected = []
                    for i, issue in enumerate(st.session_state.issues):
                        severity_map = {"Critical": ("严重", "red"), "Major": ("主要", "orange"), "Minor": ("次要", "blue")}
                        sev_label, sev_color = severity_map.get(issue["issue_type"], (issue["issue_type"], "grey"))
                        
                        col_check, col_content = st.columns([1, 9])
                        with col_check:
                            is_selected = st.checkbox("", value=(i in st.session_state.selected_indices), key=f"check-{i}")
                            if is_selected: new_selected.append(i)
                        
                        with col_content:
                            with st.expander(f"#{i+1} [{sev_label}] {issue['description'][:50]}..."):
                                st.markdown(f"**级别:** :{sev_color}[{sev_label}]")
                                st.markdown(f"**描述:** {issue['description']}")
                                st.markdown(f"**建议:** {issue['suggestion']}")
                                st.markdown(f"**原文:** `{issue['original_text']}`")
                                if st.button(f"📍 定位到原文 #{i+1}", key=f"btn-{i}"):
                                    st.session_state.scroll_to_id = i
                                    st.rerun()
                    
                    st.session_state.selected_indices = new_selected
                    
                    # Generate commented docx in memory for download
                    selected_issues = [st.session_state.issues[i] for i in st.session_state.selected_indices]
                    if selected_issues:
                        output_path = os.path.join(temp_dir, f"commented_{uploaded_file.name}")
                        try:
                            # Ensure we use a fresh copy of the original file
                            # Ensure we use a fresh copy of the original file
                            generate_commented_docx(tmp_file_path, output_path, selected_issues)
                            with open(output_path, "rb") as f:
                                st.download_button(
                                    label="📥 下载带原生批注的文档",
                                    data=f,
                                    file_name=f"审核版_{uploaded_file.name}",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    type="primary"
                                )
                            st.info("💡 提示：下载后的文档请使用 Microsoft Word 打开以查看右侧批注气泡。")
                        except Exception as e:
                            st.error(f"生成文档时出错: {str(e)}")

if __name__ == "__main__":
    main()
