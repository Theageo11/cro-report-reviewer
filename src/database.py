"""
简单的基于 JSON 的数据库管理
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import uuid


class Database:
    def __init__(self, db_dir: str = "temp_database"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)
        self.db_file = self.db_dir / "documents.json"
        self._init_db()
    
    def _init_db(self):
        """初始化数据库文件"""
        if not self.db_file.exists():
            self._save_db({"documents": []})
    
    def _load_db(self) -> Dict:
        """加载数据库"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"documents": []}
    
    def _save_db(self, data: Dict):
        """保存数据库"""
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create_document(self, filename: str, original_filename: str, file_path: str) -> str:
        """创建新文档记录"""
        db = self._load_db()
        doc_id = str(uuid.uuid4())
        
        doc = {
            "id": doc_id,
            "filename": filename,
            "original_filename": original_filename,
            "file_path": file_path,
            "status": "uploaded",  # uploaded, analyzing, analyzed
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "analysis_result": None,
            "quality_score": None,
            "issues": [],
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0
        }
        
        db["documents"].append(doc)
        self._save_db(db)
        return doc_id
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """获取文档详情"""
        db = self._load_db()
        for doc in db["documents"]:
            if doc["id"] == doc_id:
                return doc
        return None
    
    def get_all_documents(self) -> List[Dict]:
        """获取所有文档"""
        db = self._load_db()
        # 按创建时间倒序排序
        docs = sorted(db["documents"], key=lambda x: x["created_at"], reverse=True)
        return docs
    
    def update_document(self, doc_id: str, updates: Dict):
        """更新文档信息"""
        db = self._load_db()
        for i, doc in enumerate(db["documents"]):
            if doc["id"] == doc_id:
                doc.update(updates)
                doc["updated_at"] = datetime.now().isoformat()
                db["documents"][i] = doc
                self._save_db(db)
                return True
        return False
    
    def update_analysis(self, doc_id: str, issues: List[Dict], parsed_content: List[Dict]):
        """更新分析结果"""
        critical_count = sum(1 for i in issues if i["issue_type"] == "Critical")
        major_count = sum(1 for i in issues if i["issue_type"] == "Major")
        minor_count = sum(1 for i in issues if i["issue_type"] == "Minor")
        quality_score = max(0, 100 - (critical_count * 20 + major_count * 10 + minor_count * 5))
        
        updates = {
            "status": "analyzed",
            "issues": issues,
            "parsed_content": parsed_content,
            "quality_score": quality_score,
            "critical_count": critical_count,
            "major_count": major_count,
            "minor_count": minor_count
        }
        
        return self.update_document(doc_id, updates)
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        db = self._load_db()
        doc = self.get_document(doc_id)
        if doc:
            # 删除文件
            try:
                if os.path.exists(doc["file_path"]):
                    os.remove(doc["file_path"])
            except Exception:
                pass
            
            # 从数据库删除
            db["documents"] = [d for d in db["documents"] if d["id"] != doc_id]
            self._save_db(db)
            return True
        return False
    
    def get_risk_summary(self, doc_id: str) -> str:
        """获取风险摘要"""
        doc = self.get_document(doc_id)
        if not doc or doc["status"] != "analyzed":
            return "未分析"
        
        critical = doc["critical_count"]
        major = doc["major_count"]
        minor = doc["minor_count"]
        
        if critical > 0:
            return f"发现 {critical} 个严重问题"
        elif major > 0:
            return f"发现 {major} 个主要问题"
        elif minor > 0:
            return f"发现 {minor} 个次要问题"
        else:
            return "未发现问题"

