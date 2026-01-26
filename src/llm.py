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
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model or "qwen-vl-max-latest"

    def analyze_report(self, content_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Send the document content to Qwen-VL-Max for analysis using parallel batching for speed.
        """
        # 1. Split content into batches (e.g., 25 items per batch)
        batch_size = 25
        batches = [content_items[i:i + batch_size] for i in range(0, len(content_items), batch_size)]
        
        all_issues = []
        from concurrent.futures import ThreadPoolExecutor
        
        # 2. Process batches in parallel
        with ThreadPoolExecutor(max_workers=min(len(batches), 5)) as executor:
            results = list(executor.map(self._analyze_batch, batches))
            
        for batch_result in results:
            if batch_result:
                all_issues.extend(batch_result)
                
        return all_issues

    def _analyze_batch(self, batch_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Helper to analyze a single batch of content."""
        # Load review rules
        rules_path = os.path.join(os.path.dirname(__file__), "..", "config", "review_rules.md")
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                review_rules = f.read()
        except Exception:
            review_rules = "深度审核提供的临床/实验室报告，发现其中的数据矛盾和逻辑错误。"

        system_prompt = f"""你是一位专业的 CRO（合同研究组织）报告审核专家。
你的任务是根据以下审核规则深度审核提供的报告片段：

{review_rules}

**输出要求：**
请以严格的 JSON 格式输出你的发现。JSON 应为一个对象列表。
每个对象必须包含：
- "category": 问题的类别 ("text", "table", "image")。
- "element_id": 纯数字 ID。
- "original_text": 用于高亮的文本片段（必须与原文完全一致）。
- "issue_type": "Critical", "Major", "Minor"。
- "description": 中文描述。
- "suggestion": 中文建议。

**注意事项：**
- 仅分析本次提供的片段。
- 确保返回严谨的 JSON，不要包含 Markdown 代码块标记。
"""

        user_content = []
        for item in batch_items:
            prefix = f"[ID: {item['id']}] "
            if item["type"] == "text":
                user_content.append({"text": f"{prefix}{item['content']}"})
            elif item["type"] == "table":
                user_content.append({"text": f"{prefix}Table:\n{item['content']}"})
            elif item["type"] == "image":
                user_content.append({"text": prefix})
                img_data = item["path"]
                if img_data.startswith("data:image"):
                    user_content.append({"image": img_data})
                else:
                    abs_path = os.path.abspath(img_data)
                    user_content.append({"image": f"file://{abs_path}"})

        messages = [
            {"role": "system", "content": [{"text": system_prompt}]},
            {"role": "user", "content": user_content}
        ]

        try:
            response = dashscope.MultiModalConversation.call(
                model=self.model,
                api_key=self.api_key,
                messages=messages,
                result_format='message',
                max_tokens=1500
            )

            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0].message.content
                if isinstance(content, list):
                    content = "".join([b["text"] for b in content if "text" in b])
                
                content = content.strip().replace("```json", "").replace("```", "")
                return json.loads(content)
        except Exception as e:
            print(f"❌ Batch 分析失败: {e}")
        return []
