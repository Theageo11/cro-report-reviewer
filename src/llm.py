import os
import json
from typing import List, Dict, Any
from http import HTTPStatus
import dashscope
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

class QwenClient:
    def __init__(self):
        self.model = "qwen-vl-max-latest"

    def analyze_report(self, content_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Send the document content to Qwen-VL-Max for analysis.
        Returns a list of issues found.
        """
        # Load review rules from config file
        rules_path = os.path.join(os.path.dirname(__file__), "..", "config", "review_rules.md")
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                review_rules = f.read()
        except Exception:
            review_rules = "深度审核提供的临床/实验室报告，发现其中的数据矛盾和逻辑错误。"

        messages = [
            {
                "role": "system",
                "content": [
                    {"text": f"""你是一位专业的 CRO（合同研究组织）报告审核专家。
你的任务是根据以下审核规则深度审核提供的临床/实验室报告：

{review_rules}

**输出要求：**
请以严格的 JSON 格式输出你的发现。JSON 应为一个对象列表。
每个对象必须包含：
- "category": 问题的类别，必须是 "text"、"table" 或 "image" 之一。
- "element_id": 发现问题的元素 ID，必须是**纯数字**（整数类型，不要包含 "ID:" 前缀）。
    - 从输入内容的 [ID: n] 标记中提取数字 n。
    - 示例：如果看到 [ID: 63]，则 element_id 应该是 63（而不是 "ID:63" 或 "63"）。
- "original_text": 用于高亮的文本片段。
    - 如果 category 是 "text"，请提供文档中**有问题的具体片段**，而不是整段文本。
      * 必须与文档中的文本**完全一致**（包括标点符号、空格）。
      * 应该是能够唯一定位到问题位置的关键文本。
      * 示例：如果问题是"R²值标注为0.9983"，则提取 "R²值标注为0.9983" 或 "R² = 0.9983"。
    - 如果 category 是 "table"，请提供该表格的**完整名称或编号**（如"表1 验证结果汇总表"）。
    - 如果 category 是 "image"，请提供该图片的**完整标题**（如"图2 2-己基辛醇线性图谱"）。
- "issue_type": "Critical"、"Major" 或 "Minor" 之一。
- "description": 问题的详细中文描述。
- "suggestion": 如何修复该问题的中文建议。

**注意事项：**
- 忽略纯格式问题。
- 必须确保返回的 JSON 格式严谨，不要包含任何 Markdown 代码块标记。
- 所有描述和建议必须使用中文。
"""}
                ]
            }
        ]

        user_content = []
        for item in content_items:
            prefix = f"[ID: {item['id']}] "
            if item["type"] == "text":
                user_content.append({"text": f"{prefix}{item['content']}"})
            elif item["type"] == "table":
                user_content.append({"text": f"{prefix}Table:\n{item['content']}"})
            elif item["type"] == "image":
                user_content.append({"text": prefix})
                img_data = item["path"]
                if img_data.startswith("data:image"):
                    # It's a base64 data URI from mammoth
                    user_content.append({"image": img_data})
                else:
                    abs_path = os.path.abspath(img_data)
                    user_content.append({"image": f"file://{abs_path}"})

        messages.append({
            "role": "user",
            "content": user_content
        })

        try:
            response = dashscope.MultiModalConversation.call(
                model=self.model,
                messages=messages,
                result_format='message',
                max_tokens=2000
            )

            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0].message.content
                if isinstance(content, list):
                    text_content = ""
                    for block in content:
                        if "text" in block:
                            text_content += block["text"]
                    content = text_content
                
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return []
            else:
                return []
        except Exception as e:
            print(f"❌ LLM 分析失败: {e}")
            return []
