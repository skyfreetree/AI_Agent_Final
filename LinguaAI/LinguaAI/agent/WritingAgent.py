import requests
import json
from dataclasses import dataclass
import openai
from LinguaAI.prompts import WRITING_PROMPTS
from LinguaAI.error_books import WritingErrorBook
from LinguaAI.database import ChatDatabase

scene_db = ChatDatabase()
db_settings = scene_db.get_settings()



writing_error_book = WritingErrorBook()

class WritingAgent:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=db_settings["api_key"],
            base_url=db_settings["host"]
        )
        
    def generate_question(self, task: str):
        print('writing generate_question task', task)
        prompt = WRITING_PROMPTS["generate"].format(goal=task)
        print('writing generate_question prompt', prompt)
        response = self.client.chat.completions.create(
            model=db_settings["model_name"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )
        print('writing generate_question', response.choices[0].message.content.strip())
        return response.choices[0].message.content.strip()

    def check_grammar(self, text: str):
        """检查语法错误并提供改进建议，返回结构化 JSON 列表"""
        print('开始检查语法错误')
        prompt = WRITING_PROMPTS["grammar"].format(text=text)
        print('writing check_grammar prompt', prompt)
        for i in range(3):
            response = self.client.chat.completions.create(
                model=db_settings["model_name"],
                messages=[{"role": "user", "content": prompt}],
            )
            print('writing check_grammar response', response.choices[0].message.content.strip())
            try:
                errors = response.choices[0].message.content.strip()
                return errors
            except Exception:
                print(f'第{i+1}次检查语法错误失败')
                continue
            



    def review_and_score_writing(self, user_input, scenario):
        prompt = WRITING_PROMPTS["review"].format(scenario=scenario, user_input=user_input)
        print('writing review_and_score_writing prompt', prompt)
        messages = [{"role": "user", "content": prompt}]
        
        for i in range(3):
            result = self.client.chat.completions.create(
                model=db_settings["model_name"],
                messages=messages,
                response_format={"type": "json_object"}
            )

            try:
                review_json = json.loads(result.choices[0].message.content.strip())
                print('writing review_and_score_writing response', review_json)
                score = review_json.get("score")
                if score is not None and score < 60:
                    writing_error_book.add_error(
                        topic=scenario,
                        user_essay=user_input,
                        model_essay=review_json.get("model_answer", ""),
                        error_type="分数低",
                        error_description=f"AI批改得分为{score}分，低于及格线"
                    )
                breakdown = review_json.get("breakdown", {})
                breakdown_str = "\n".join([f"{k}: {v}分" for k, v in breakdown.items()])
                feedback = review_json.get("feedback", "")
                model_answer = review_json.get("model_answer", "")
                summary = (
                    f"评分：{score}分\n"
                    f"各项评分：\n{breakdown_str}\n\n"
                    f"评语：{feedback}\n\n"
                    f"参考范文：\n{model_answer}"
                )
                return summary
            except Exception:
                print(f'第{i+1}次评分失败')
                continue
        return "评分失败，请稍后重试。"

        
    