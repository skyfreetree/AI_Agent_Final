READING_PROMPT = {
    "evaluate_understanding": """
        请作为一位英语阅读老师，评估学生对以下英语文章的理解：
        文章内容：
        {content}

        学生的理解总结：
        {user_summary}

        请从以下几个方面进行评估：
        1. 理解准确度（0-1分）
        2. 主要观点是否完整
        3. 是否有理解偏差或错误
        4. 具体改进建议
        5. 如果学生理解有误，请提供正确的理解

        请用中文回复，格式如下：
        {{
            "understanding_score": 分数,
            "main_points": ["要点1", "要点2", ...],
            "misunderstandings": ["误解1", "误解2", ...],
            "suggestions": ["建议1", "建议2", ...],
            "correct_understanding": "如果学生理解有误，这里提供正确的理解",
            "detailed_feedback": "详细的反馈内容，包括对错误理解的纠正和正确的理解说明"
        }}"""
}
