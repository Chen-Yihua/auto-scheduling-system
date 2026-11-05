TASK_FIELD_INFERENCE_PROMPT = """
你是任務規劃助手。使用者建立了一個任務，但不確定優先程度或預估花費時間，
請根據標題、描述、以及使用者給的提醒，推斷合理的值，並用一句話簡短說明理由。
使用者的提醒如果跟標題/描述看起來的難度不一致，以使用者的提醒為準。

標題：{title}
描述：{description}
使用者給的提醒：{hint}

請只輸出 JSON，格式為：
{{"priority": "High" 或 "Medium" 或 "Low", "duration_minutes": 整數, "reason": "一句話說明理由"}}
不要輸出任何說明文字或 markdown 標記。
"""

SUBTASK_FIELD_INFERENCE_PROMPT = """
你是任務規劃助手。使用者把一個主任務拆成幾個依序進行的階段（子任務），
其中下面這些子任務不確定優先程度或預估花費時間。請參考主任務的標題和描述，
逐一推斷每個子任務合理的值，並各用一句話簡短說明理由。
子任務自己的提醒如果跟標題/描述看起來的難度不一致，以提醒為準。

主任務標題：{parent_title}
主任務描述：{parent_description}

要推斷的子任務（依序）：
{subtasks}

請只輸出 JSON 陣列，依上面的順序每個子任務一筆，筆數要和子任務數量相同，每筆格式為：
{{"priority": "High" 或 "Medium" 或 "Low", "duration_minutes": 整數, "reason": "一句話說明理由"}}
不要輸出任何說明文字或 markdown 標記。
"""

SUBTASK_LINE = "{number}. 標題：{title}；描述：{description}；提醒：{hint}"
