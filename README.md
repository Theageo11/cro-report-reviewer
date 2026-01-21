# CRO 报告审核系统

基于文档内容的多模态审核系统，专注于检查报告中的数据一致性、计算准确性和表述规范性。

## ✨ 核心功能

- ✅ **数据一致性检查** - 检查文档内部数据是否一致
- ✅ **计算准确性验证** - 验证关键指标计算是否正确（RSD、回收率等）
- ✅ **表述规范性检查** - 检查专业术语和表述规范
- ✅ **多模态支持** - 同时处理文本和图片内容
- ✅ **格式支持** - 支持 .docx、.pdf、.xlsx 格式

## 🚀 快速开始

### 1. 环境准备

```bash
# 进入项目目录
cd cro-report-reviewer

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 方法1: 设置环境变量
export DASHSCOPE_API_KEY=your_api_key_here

# 方法2: 创建 .env 文件
echo "DASHSCOPE_API_KEY=your_api_key_here" > .env
```

**获取 API Key**:
1. 访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/)
2. 注册/登录阿里云账号
3. 创建 API Key
4. 复制 Key 到环境变量或 .env 文件

### 3. 运行系统

```bash
streamlit run app.py
```

访问: `http://localhost:8501`

## 🏗️ 项目结构

```
cro-report-reviewer/
├── src/                    # 源代码目录
│   ├── document_parser.py  # 文档解析器
│   ├── rule_engine.py      # 规则引擎
│   ├── llm_client.py       # LLM 客户端
│   └── analyzer.py         # 分析器
├── tests/                  # 测试目录
├── knowledge_base/         # 知识库（预留）
├── temp/                   # 临时文件目录
├── app.py                 # Streamlit 主应用
├── requirements.txt       # 依赖列表
└── README.md             # 说明文档
```

## 🔧 技术栈

- **前端框架**: Streamlit >=1.30.0
- **文档解析**: python-docx, PyMuPDF, openpyxl
- **数据处理**: pandas, numpy, scipy
- **多模态模型**: Qwen-VL-Max (通过 dashscope)
- **数据验证**: pydantic

## 📊 审核规则

### 数据一致性检查
- 对照品信息一致性
- 供试品信息一致性  
- 仪器信息一致性
- 表格数据与正文一致性

### 计算准确性验证
- RSD 计算验证
- 回收率计算验证
- 线性方程验证
- 统计计算验证

### 表述规范性检查
- 专业术语规范
- 表述清晰准确
- 避免模糊表述
- 结论明确性

## 💰 成本估算

基于 Qwen-VL-Max 定价：
- 纯文本审核: ~¥0.54/份
- 含图片审核: ~¥0.57/份

## 🎯 使用场景

1. **CRO 报告质量审核**
2. **学术论文格式检查**
3. **技术文档规范性验证**
4. **数据分析报告审核**

## ⚠️ 注意事项

1. API Key 需要正确设置才能使用 LLM 功能
2. 系统完全基于文档内容检查，不依赖外部知识库
3. 图片审核需要额外的 API 调用费用
4. 建议在审核前备份重要文档

## 🤝 开发指南

### 添加新的检查规则

在 `src/rule_engine.py` 中添加新的规则类：

```python
class NewCheckRule:
    def check(self, document):
        # 实现检查逻辑
        return comments
```

### 扩展文档格式支持

在 `src/document_parser.py` 中添加新的解析方法：

```python
def _parse_new_format(self, file_path):
    # 实现新格式解析
    return result
```

## 📝 版本历史

- v1.0.0 (2026-01-21): 初始版本发布
  - 支持 .docx, .pdf, .xlsx 格式
  - 实现基础规则检查
  - 集成 Qwen-VL-Max 多模态审核

## 📞 支持

如有问题或建议，请提交 Issue 或联系开发团队。