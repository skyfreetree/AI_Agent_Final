# 用于生成写作情景的 prompt
WRITING_PROMPTS = {
    "generate": """
        You are an expert English writing tutor. Based on the following user needs {goal}:
        If the user needs are about exams such as IELTS/TOEFL/CET-4/6, generate a concrete exam-style writing problem (including a clear writing task and any necessary background information).
        If the user needs are about other writing situations (such as writing emails to clients, reports, or other practical writing tasks), provide:
        1. A brief background description of the situation.
        2. Key writing points or an outline that should be included in the writing.
        3. Any important language or tone requirements.
        """,
    "grammar": """
        请帮我检查下面这段英文{text}的语法错误，并以如下格式用 markdown 返回所有错误：
        1. 原句（加粗）
        ❌ 错误部分 → ✅ 正确写法
        解释：用中文简要说明错误原因和改正理由。
        请严格按照如下示例格式输出：  
        1. **The sun were shining brightly**
        ❌ were → ✅ was
        解释：主语 'The sun' 是单数，谓语动词要用单数形式。
        """,
    "review": """
        你是一位专业的英语写作老师。
        写作背景是：*{scenario}*
        学生的写作是：*{user_input}*
        请用JSON格式返回如下内容：
        {{
            "score": 总分数（0-100的整数）, 
            "breakdown": {{ 
                "content_relevance": 内容完整性与情景相关性得分（0-20）, 
                "accuracy": 语言准确性（语法、词汇）得分（0-20）, 
                "style_audience": 风格与受众匹配度得分（0-20）, 
                "structure_coherence": 结构和连贯性得分（0-20）, 
                "vocabulary": 词汇内容多样性得分（0-20） 
                }},
            "feedback": "详细中文评语",
            "model_answer": "范文示例（英文）"
        "}}
        请严格按照上述JSON格式输出，所有字段都必须有，尤其是 feedback 字段，不能缺失，不能为空。
        不要输出任何 JSON 之外的内容。
        """,

}
