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

def get_analysis(content_items, use_mock=False):
    """
    分析文档内容
    :param content_items: 文档内容列表
    :param use_mock: 是否使用 Mock 模式（调试用）
    """
    import json
    mock_file = "mock_analysis_result.json"

    if use_mock and os.path.exists(mock_file):
        # Mock 模式：加载保存的结果
        with open(mock_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # 真实模式：调用 LLM
    llm_client = QwenClient()
    result = llm_client.analyze_report(content_items)

    # 保存结果供后续 Mock 使用
    try:
        with open(mock_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result

def highlight_text(html_content, issues, active_id=None):
    """高亮显示文档中的问题位置，支持文本、表格名和图片分类高亮"""
    if not issues:
        return html_content
        
    from bs4 import BeautifulSoup
    import re
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for i, issue in enumerate(issues):
        try:
            category = issue.get("category", "text")
            eid = int(issue.get("element_id", -1))
            text_to_highlight = issue.get("original_text", "").strip()
            
            color = "#fef3c7" # Default Major (Yellow)
            border_color = "#f59e0b"
            if issue["issue_type"] == "Critical":
                color = "#fee2e2" # Red
                border_color = "#ef4444"
            elif issue["issue_type"] == "Minor":
                color = "#e0f2fe" # Blue
                border_color = "#3b82f6"
            
            is_active = (active_id == i)
            anchor_id = f"issue-{i}"
            
            if category == "image" and eid != -1:
                # 图片高亮：直接定位到图片元素
                target_tag = soup.find(id=f"doc-el-{eid}")
                if target_tag:
                    target_tag['id'] = anchor_id
                    active_style = "outline: 5px solid #ef4444; outline-offset: 5px;" if is_active else f"outline: 3px solid {border_color};"
                    target_tag['style'] = target_tag.get('style', '') + f"; {active_style}"
            
            elif (category == "text" or category == "table") and text_to_highlight:
                # 文本或表格名高亮：在全文中搜索文本片段
                # 我们优先在 element_id 对应的标签中找，找不到再全局找
                found = False
                search_tags = []
                if eid != -1:
                    marker = soup.find(id=f"doc-el-{eid}")
                    if marker: search_tags.append(marker.parent)
                
                if not search_tags:
                    search_tags = soup.find_all(['p', 'td', 'th', 'h1', 'h2', 'h3', 'li'])
                
                for tag in search_tags:
                    for text_node in tag.find_all(string=True):
                        if text_to_highlight in text_node:
                            active_style = "outline: 4px solid #ef4444; outline-offset: 2px; box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);" if is_active else ""
                            highlight_html = f'<span id="{anchor_id}" style="background-color: {color}; border-bottom: 2px solid {border_color}; font-weight: bold; {active_style}">{text_to_highlight}</span>'
                            new_content = text_node.replace(text_to_highlight, highlight_html)
                            new_soup = BeautifulSoup(new_content, 'html.parser')
                            text_node.replace_with(new_soup)
                            found = True
                            break
                    if found: break
                
                if not found and eid != -1:
                    # 如果没找到文本，但有 ID，则对整个元素进行兜底高亮
                    target_tag = soup.find(id=f"doc-el-{eid}")
                    if target_tag:
                        target_tag['id'] = anchor_id
                        active_style = "outline: 4px solid #ef4444; outline-offset: 2px;" if is_active else ""
                        target_tag['style'] = target_tag.get('style', '') + f"; background-color: {color}; border-left: 4px solid {border_color}; padding: 4px; {active_style}"
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
                <div class="feature-label">(In progress)</div>
            </div>
            <div class="feature-item">  
                <div class="feature-icon">✓</div>
                <div class="feature-label">表述规范性审核</div>
                <div class="feature-label">(In progress)</div>
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
        st.markdown("""
        <div style="background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(20px); border-radius: 16px; color:#6B7280; margin-bottom: 1rem;
                    text-align: center; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16); border: 1px solid rgba(255, 255, 255, 0.2);">
            <span style="font-size: 1.2rem; font-weight: 600;">上传报告文档</span>
        </div>
        """, unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "上传报告文档",
            type=["docx"],
            help="支持 DOCX 格式，最大 200MB",
            label_visibility="collapsed"
        )

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
        col1, col2 = st.columns([7, 3])

        with col1:
            st.markdown('<h3 class="card-title">文档预览</h3>', unsafe_allow_html=True)

            if not st.session_state.html_content:
                with st.spinner("正在解析文档..."):
                    doc_data = get_doc_data(tmp_file_path)
                    st.session_state.html_content = doc_data["html"]
                    st.session_state.parsed_content = doc_data["content"]
            
            display_html = st.session_state.html_content
            if st.session_state.issues:
                display_html = highlight_text(display_html, st.session_state.issues, active_id=st.session_state.scroll_to_id)
            
            render_document_preview(display_html, st.session_state.scroll_to_id)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            # Mock 模式开关
            st.markdown('<div style="margin-bottom: 1rem;">', unsafe_allow_html=True)
            
            # 初始化 use_mock 状态
            if 'use_mock' not in st.session_state:
                st.session_state.use_mock = False
            
            use_mock = st.checkbox(
                "🧪 使用 Mock 模式（调试用，不消耗 tokens）",
                value=st.session_state.use_mock,
                help="启用后将使用已保存的分析结果，不调用 LLM API",
                key="mock_mode_checkbox"
            )
            st.session_state.use_mock = use_mock
            
            if use_mock:
                if os.path.exists("mock_analysis_result.json"):
                    st.info("💡 Mock 模式已启用：将使用已保存的分析结果")
                else:
                    st.warning("⚠️ 尚无保存的结果，首次分析将调用真实 LLM 并保存结果")
            st.markdown('</div>', unsafe_allow_html=True)
            
            col_btn1, col_btn2 = st.columns([2, 1])
            with col_btn1:
                if st.button("开始智能分析", type="primary", use_container_width=True):
                    st.session_state.analyzing = True
                    st.rerun()
            with col_btn2:
                if st.button("🔄 重置", help="清除缓存并重新开始", use_container_width=True):
                    st.cache_data.clear()
                    st.session_state.issues = None
                    st.session_state.html_content = ""
                    st.session_state.highlighted_html = ""
                    st.rerun()

            if st.session_state.analyzing:
                render_ai_thinking()
                try:
                    st.session_state.issues = get_analysis(
                        st.session_state.parsed_content,
                        use_mock=st.session_state.use_mock
                    )
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

                    # Issue selection and display
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
                        st.info(f"已选择 {len(selected_issues)} 个问题")

                        # 用户点击按钮后才生成文档
                        if st.button("生成审核报告", type="primary", use_container_width=True):
                            with st.spinner("正在生成审核报告..."):
                                output_path = os.path.join(temp_dir, f"commented_{uploaded_file.name}")
                                try:
                                    generate_commented_docx(tmp_file_path, output_path, selected_issues)
                                    with open(output_path, "rb") as f:
                                        file_data = f.read()

                                    # 存储到session state中，避免重复生成
                                    st.session_state.generated_file = file_data
                                    st.session_state.generated_filename = f"审核版_{uploaded_file.name}"
                                    st.success("✅ 报告生成成功！")
                                except Exception as e:
                                    st.error(f"生成文档出错: {str(e)}")

                        # 如果已经生成过文档，显示下载按钮
                        if hasattr(st.session_state, 'generated_file') and st.session_state.generated_file:
                            st.download_button(
                                label="📥 下载审核报告",
                                data=st.session_state.generated_file,
                                file_name=st.session_state.generated_filename,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )
                            st.info("💡 提示：请使用 Microsoft Word 打开查看右侧批注气泡")

            st.markdown('</div>', unsafe_allow_html=True)

    else:
        render_empty_state()

if __name__ == "__main__":
    main()
