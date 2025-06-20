PLANNING_PROMPT = {
    "analyze_needs": """请分析以下学习需求*{user_input}*，并确定需要使用阅读、写作、听力中的哪些学习模块（可以只选择一个模块）。
        返回JSON格式，包含以下字段：
        - modules: 需要使用的模块列表，按照重要程度顺序（["reading", "writing", "listening"]）
        - tasks: 每个模块的具体任务描述
        
        注意：
        1. 对于考试类需求（如高考、雅思、托福等），请针对题型来选择需要哪里模块
        2. 对于特定技能提升需求，针对性选择相关模块
        3. 确保每个提到的需求都有对应的模块和任务
        4. 任务描述要具体且符合考试特点
        
        输出示例：
        {{
            "modules": ["listening", "reading", "writing"],
            "tasks": {{
                "listening": "雅思听力训练，包括对话、讲座和学术讨论",
                "reading": "雅思阅读理解练习，包括学术文章和图表理解",
                "writing": "雅思写作训练，包括图表描述和议论文写作"
            }},
        }}
        """,
    "generate_keywords_for_reading": """
            请根据以下学习需求*{task}*，生成3个不同的英语文章搜索关键词，关键词长度不超过两个单词。
            要求：
            1. 每个关键词要具体且相关，但角度不同
            2. 使用英文关键词
            3. 如果是考试相关，要包含考试类型和具体题型
            4. 如果是特定主题，要包含主题名称
            5. 关键词要适合英语学习者的水平
            6. 返回格式为JSON数组，例如：["keyword1", "keyword2", "keyword3"]
            
            只需返回JSON数组，不要其他内容。
            """,
    "generate_keywords_for_listening": """请根据以下学习需求，生成3个不同的英语听力材料搜索关键词。
        要求：
        1. 每个关键词要具体且相关，但角度不同
        2. 使用英文关键词
        3. 如果是考试相关，要使得关键词可以找到和考试真题文章相关的材料
        4. 如果是特定主题，要包含主题名称
        5. 关键词要适合英语学习者的水平
        6. 返回格式为JSON数组，例如：["keyword1", "keyword2", "keyword3"]
        
        学习需求：{task}
        
        只需返回JSON数组，不要其他内容。""",
    
}
