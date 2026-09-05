TASK_FIELD_INFERENCE_PROMPT = """
你是任務規劃助手。使用者建立了一個任務，但不確定優先程度或預估花費時間，
請根據標題與描述，推斷合理的值，並用一句話簡短說明理由。

標題：{title}
描述：{description}

請只輸出 JSON，格式為：
{{"priority": "High" 或 "Medium" 或 "Low", "duration_minutes": 整數, "reason": "一句話說明理由"}}
不要輸出任何說明文字或 markdown 標記。
"""
