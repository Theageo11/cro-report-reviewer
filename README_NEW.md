# 明捷医药报告审核Demo

基于 Flask 的 Web 应用，用于审核 CRO 报告文档。

## 功能特性

- 📤 **文档上传**：支持 DOCX 格式文档上传
- 🤖 **AI 智能分析**：使用多模态 AI 分析文档内容，检测问题
- 📊 **质量评分**：自动计算文档质量评分
- 🔍 **问题高亮**：在文档中高亮显示问题位置
- 📥 **导出报告**：下载带批注的 Word 文档

## 系统架构

### 页面结构

- **Dashboard**（开发中）
- **Documents**（可用）- 主要功能页面
  - 文档列表视图
  - 文档详情视图
- **Knowledge Base**（开发中）
- **Settings**（开发中）

### 技术栈

- **后端**：Flask 3.0
- **前端**：HTML5 + CSS3 + JavaScript（原生）
- **AI**：通义千问多模态大模型
- **数据存储**：JSON 文件
- **文档处理**：python-docx, mammoth

## 安装说明

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件，添加以下内容：

```
DASHSCOPE_API_KEY=your_api_key_here
```

### 3. 运行应用

```bash
python app_flask.py
```

应用将在 http://localhost:5001 启动

## 使用说明

### 上传文档

1. 在 Documents 页面点击"上传文档"按钮
2. 选择 DOCX 格式的报告文档
3. 等待上传完成

### 分析文档

1. 在文档卡片上点击"开始分析"按钮
2. AI 将自动分析文档内容
3. 分析完成后查看质量评分和问题列表

### 查看详情

1. 点击文档卡片进入详情页
2. 左侧显示文档内容（带高亮的问题位置）
3. 右侧显示问题列表
4. 点击"定位到原文"可跳转到对应位置

### 下载报告

1. 在详情页点击"下载审核报告"按钮
2. 系统将生成带批注的 Word 文档
3. 使用 Microsoft Word 打开查看批注

## 目录结构

```
.
├── app_flask.py          # Flask 应用主文件
├── src/
│   ├── database.py       # 数据库管理
│   ├── parser.py         # 文档解析器
│   ├── llm.py           # LLM 客户端
│   └── commenter.py     # 批注生成器
├── templates/           # HTML 模板
│   ├── base.html       # 基础模板
│   ├── documents.html  # 文档列表页
│   ├── document_detail.html  # 文档详情页
│   └── placeholder.html # 占位页面
├── static/
│   └── styles_new.css  # 样式文件
├── temp_docs/          # 临时文档存储
├── temp_database/      # 数据库文件
└── config/
    └── review_rules.md # 审核规则
```

## API 端点

- `GET /` - 重定向到文档页面
- `GET /documents` - 文档列表页面
- `GET /documents/<doc_id>` - 文档详情页面
- `POST /api/upload` - 上传文档
- `POST /api/analyze/<doc_id>` - 分析文档
- `DELETE /api/documents/<doc_id>` - 删除文档
- `GET /api/download/<doc_id>` - 下载审核报告

## 配色方案

- **高风险**：粉红色 (#FF6B6B)
- **中风险**：橙色 (#FF9F66)
- **低风险**：绿色 (#66D9A6)
- **已批准**：蓝色 (#66B3FF)
- **主色调**：青色 (#00BFA6)

## 注意事项

- 文档和数据存储在本地临时目录中
- 支持的文档格式：DOCX
- 最大文件大小：200MB
- 建议使用 Chrome、Safari 或 Edge 浏览器

## 开发说明

### 旧版本迁移

旧版本使用 Streamlit（`app.py`），新版本使用 Flask（`app_flask.py`）。
旧版本的功能已完全迁移到新版本。

### Mock 模式

在分析文档时，可以通过修改前端代码启用 Mock 模式，使用本地保存的分析结果，避免消耗 API tokens。

```javascript
// 在 documents.html 或 document_detail.html 中修改
body: JSON.stringify({ use_mock: true })  // 启用 Mock 模式
```

## License

MIT

