LISTENING_PROMPT = {
    "evaluate_intensive": """
                        请作为一位英语听力老师，评估学生的听写内容：
                        原始内容：
                        {original_content}

                        学生的听写：
                        {user_transcript}

                        请从以下几个方面进行评估：
                        1. 听写准确度（0-1分）
                        2. 拼写错误
                        3. 语法错误
                        4. 漏听或误听的内容
                        5. 具体改进建议

                        请用中文回复，格式如下：
                        {{
                            "accuracy_score": 分数,
                            "spelling_errors": ["错误1", "错误2", ...],
                            "grammar_errors": ["错误1", "错误2", ...],
                            "missing_content": ["漏听内容1", "漏听内容2", ...],
                            "suggestions": ["建议1", "建议2", ...],
                            "detailed_feedback": "详细的反馈内容"
                        }}""",
    "evaluate_extensive": """
                        请作为一位英语听力老师，评估学生对以下英语听力材料的理解：
                        听力材料内容：
                        {original_content}

                        学生的理解总结：
                        {user_summary}

                        请从以下几个方面进行评估：
                        1. 理解准确度（0-100分）
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
                            "detailed_feedback": "详细的反馈内容"
                        }}""",

}