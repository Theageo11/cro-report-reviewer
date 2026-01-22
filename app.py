import streamlit as st
import os
import tempfile
from pathlib import Path
from src.parser import DocxParser
from src.llm import QwenClient
from src.commenter import generate_commented_docx
import streamlit.components.v1 as components

st.set_page_config(
    page_title="CRO 报告审核 Agent",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def load_css():
    """加载外部 CSS 文件"""
    css_file = Path(__file__).parent / "static" / "styles.css"
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

@st.cache_data
def get_doc_data(file_path):
    parser = DocxParser()
    return parser.get_content_and_html(file_path)

@st.cache_data
def get_analysis(content_items):
    print('开始分析文档...')
    print(content_items)
    llm_client = QwenClient()
    return llm_client.analyze_report(content_items)

def highlight_text(html_content, issues):
    """高亮显示文档中的问题位置"""
    if not issues:
        return html_content
        
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for i, issue in enumerate(issues):
        try:
            eid = int(issue.get("element_id", -1))
            if eid == -1:
                continue
            
            color = "yellow"
            if issue["issue_type"] == "Critical":
                color = "#fee2e2"
            elif issue["issue_type"] == "Major":
                color = "#fef3c7"
                
            target_tag = soup.find(id=f"doc-el-{eid}")
            if target_tag:
                target_tag['style'] = target_tag.get('style', '') + f"; background-color: {color}; border-left: 4px solid #ef4444; padding: 8px;"
                target_tag['id'] = f"issue-{i}"
        except Exception:
            continue
                
    return str(soup)


def render_stats(issues):
    """渲染统计信息面板"""
    if issues is None:
        return
    
    critical_count = sum(1 for i in issues if i["issue_type"] == "Critical")
    major_count = sum(1 for i in issues if i["issue_type"] == "Major")
    minor_count = sum(1 for i in issues if i["issue_type"] == "Minor")
    total_count = len(issues)
    
    quality_score = max(0, 100 - (critical_count * 20 + major_count * 10 + minor_count * 5))
    
    st.markdown(f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon">📊</div>
            <div class="stat-value">{quality_score}</div>
            <div class="stat-label">质量评分</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">🔴</div>
            <div class="stat-value">{critical_count}</div>
            <div class="stat-label">严重问题</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">🟡</div>
            <div class="stat-value">{major_count}</div>
            <div class="stat-label">主要问题</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">🔵</div>
            <div class="stat-value">{minor_count}</div>
            <div class="stat-label">次要问题</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_ai_thinking():
    """渲染 AI 分析中的状态"""
    st.markdown("""
    <div class="ai-thinking">
        <div class="thinking-animation">
            <div class="thinking-dot"></div>
            <div class="thinking-dot"></div>
            <div class="thinking-dot"></div>
        </div>
        <div class="thinking-text">AI 正在深度分析文档内容</div>
    </div>
    """, unsafe_allow_html=True)

def render_empty_state():
    """渲染空状态页面"""
    st.markdown("""
    <div class="glass-card empty-state">
        <div class="empty-state-icon">📄</div>
        <h2 class="empty-state-title">欢迎使用 AI 报告审核系统</h2>
        <div class="empty-state-description">
            上传您的 CRO 报告文档，AI 将自动检查数据一致性、计算准确性和表述规范性，
            帮助您快速发现文档中的潜在问题
        </div>
        <div class="feature-list">
            <div class="feature-item">
                <div class="feature-icon">✓</div>
                <div class="feature-label">数据一致性检查</div>
            </div>
            <div class="feature-item">
                <div class="feature-icon">✓</div>
                <div class="feature-label">计算准确性验证</div>
            </div>
            <div class="feature-item">
                <div class="feature-icon">✓</div>
                <div class="feature-label">表述规范性审核</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_document_preview(html_content, scroll_to_id=None):
    """渲染文档预览"""
    scroll_js = ""
    if scroll_to_id is not None:
        scroll_js = f"""
        <script>
            window.onload = function() {{
                setTimeout(function() {{
                    var element = document.getElementById('issue-{scroll_to_id}');
                    if (element) {{
                        element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                        element.style.outline = '4px solid #ef4444';
                        setTimeout(function() {{ element.style.outline = 'none'; }}, 2000);
                    }}
                }}, 100);
            }};
        </script>
        """
    
    preview_html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                padding: 1.5rem;
                background-color: white;
                margin: 0;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 1rem;
            }}
            th, td {{
                border: 1px solid #e5e7eb;
                padding: 0.75rem;
                text-align: left;
            }}
            tr:nth-child(even) {{
                background-color: #f9fafb;
            }}
            img {{
                max-width: 100%;
                height: auto;
                display: block;
                margin: 1rem 0;
                border-radius: 8px;
            }}
        </style>
    </head>
    <body>
        {scroll_js}
        {html_content}
    </body>
    </html>
    """
    
    components.html(preview_html, height=750, scrolling=True)

def main():
    load_css()
    
    # 创建头部容器，包含标题和上传器
    header_col1, header_col2 = st.columns([7, 3])
        
    with header_col1:
        st.markdown("""
        <div style="background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(20px); border-radius: 16px; 
                    padding: 2.5rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16); border: 1px solid rgba(255, 255, 255, 0.2);">
            <h1 class="app-title">CRO 报告审核 Agent</h1>
            <p class="app-subtitle">
                基于多模态 AI 的智能文档审核系统 · 数据一致性检查 · 计算准确性验证 · 逻辑规范性审核
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with header_col2:
        # st.markdown("""
        # <div style="background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(20px); border-radius: 16px; 
        #             padding: 2.5rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16); border: 1px solid rgba(255, 255, 255, 0.2); 
        #             height: 100%; display: flex; align-items: center;">
        # """, unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "上传报告文档",
            type=["docx"],
            help="支持 DOCX 格式，最大 200MB",
            label_visibility="visible"
        )
        # st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div style="margin-bottom: 2rem;"></div>', unsafe_allow_html=True)

    if uploaded_file:
        temp_dir = tempfile.gettempdir()
        tmp_file_path = os.path.join(temp_dir, f"uploaded_{uploaded_file.name}")
        with open(tmp_file_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        # 状态管理
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
        if 'analyzing' not in st.session_state:
            st.session_state.analyzing = False

        # 显示统计信息
        if st.session_state.issues is not None and len(st.session_state.issues) > 0:
            render_stats(st.session_state.issues)

        # 布局
        col1, col2 = st.columns([6, 4])

        with col1:
            st.markdown('<h3 class="card-title">文档预览</h3>', unsafe_allow_html=True)
            
            if not st.session_state.html_content:
                with st.spinner("正在解析文档..."):
                    doc_data = get_doc_data(tmp_file_path)
                    st.session_state.html_content = doc_data["html"]
                    st.session_state.parsed_content = doc_data["content"]
            
            display_html = st.session_state.html_content
            if st.session_state.issues:
                display_html = highlight_text(display_html, st.session_state.issues)
            
            render_document_preview(display_html, st.session_state.scroll_to_id)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            if st.button("开始智能分析", type="primary", use_container_width=True):
                st.session_state.analyzing = True
                st.rerun()
            
            if st.session_state.analyzing:
                render_ai_thinking()
                try:
                    st.session_state.issues = get_analysis(st.session_state.parsed_content)
                    st.session_state.scroll_to_id = None
                    st.session_state.selected_indices = list(range(len(st.session_state.issues)))
                    st.session_state.analyzing = False
                    st.success("分析完成")
                except Exception as e:
                    st.error(f"分析出错: {str(e)}")
                    st.session_state.issues = []
                    st.session_state.analyzing = False
                st.rerun()
            
            if st.session_state.issues is not None and not st.session_state.analyzing:
                if not st.session_state.issues:
                    st.markdown("""
                    <div class="success-state">
                        <h2>文档质量优秀</h2>
                        <p>未发现严重问题</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="issues-header">发现 {len(st.session_state.issues)} 个问题，请勾选需要保留的批注</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="issues-container">', unsafe_allow_html=True)
                    
                    new_selected = []
                    for i, issue in enumerate(st.session_state.issues):
                        severity_map = {
                            "Critical": ("严重", "critical"),
                            "Major": ("主要", "major"),
                            "Minor": ("次要", "minor")
                        }
                        sev_label, sev_class = severity_map.get(
                            issue["issue_type"],
                            (issue["issue_type"], "")
                        )
                        
                        col_check, col_content = st.columns([1, 11])
                        with col_check:
                            is_selected = st.checkbox(
                                f"问题 {i+1}",
                                value=(i in st.session_state.selected_indices),
                                key=f"check-{i}",
                                label_visibility="collapsed"
                            )
                            if is_selected:
                                new_selected.append(i)
                        
                        with col_content:
                            with st.expander(f"#{i+1} {issue['description'][:60]}...", expanded=False):
                                st.markdown(f'<span class="issue-badge {sev_class}">{sev_label}</span>', unsafe_allow_html=True)
                                st.markdown(f"**问题描述**")
                                st.write(issue['description'])
                                st.markdown(f"**修改建议**")
                                st.write(issue['suggestion'])
                                st.markdown(f"**原文内容**")
                                st.code(issue['original_text'], language="text")
                                
                                if st.button("定位到原文", key=f"btn-{i}", use_container_width=True):
                                    st.session_state.scroll_to_id = i
                                    st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.session_state.selected_indices = new_selected
                    
                    # 生成带批注的文档
                    selected_issues = [st.session_state.issues[i] for i in st.session_state.selected_indices]
                    if selected_issues:
                        st.markdown("---")
                        output_path = os.path.join(temp_dir, f"commented_{uploaded_file.name}")
                        try:
                            generate_commented_docx(tmp_file_path, output_path, selected_issues)
                            with open(output_path, "rb") as f:
                                st.download_button(
                                    label="下载审核报告",
                                    data=f,
                                    file_name=f"审核版_{uploaded_file.name}",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    type="primary",
                                    use_container_width=True
                                )
                            st.info("提示：请使用 Microsoft Word 打开查看右侧批注气泡")
                        except Exception as e:
                            st.error(f"生成文档出错: {str(e)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        render_empty_state()

if __name__ == "__main__":
    main()
