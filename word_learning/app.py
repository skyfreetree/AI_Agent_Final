from flask import Flask, render_template, jsonify, request, redirect, url_for
import json
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from planagent import StudyPlan, WordPlan, ReviewDate, Base, WordPlanner

app = Flask(__name__)

# 数据库设置
DB_PATH = 'word_plans.db'
engine = create_engine(f'sqlite:///{DB_PATH}')
Session = sessionmaker(bind=engine)

# 词库配置
DICTIONARIES = {
    'gre': {
        'name': 'GRE词库',
        'file': 'data/gre.json'
    },
    'it': {
        'name': '计算机专业英语',
        'file': 'data/it.json'
    },
    'ai': {
        'name': '人工智能词汇',
        'file': 'data/ai.json'
    },
    'kaoyan': {
        'name': '考研词库',
        'file': 'data/kaoyan.json'
    },
    'level6': {
        'name': '六级词库',
        'file': 'data/level6.json'
    },
    'level4': {
        'name': '专四词库',
        'file': 'data/level4.json'
    },
    'level8': {
        'name': '专八词库',
        'file': 'data/level8.json'
    },
    'ielts': {
        'name': '雅思词库',
        'file': 'data/ielts.json'
    },
    'toefl': {
        'name': '托福词库',
        'file': 'data/toefl.json'
    }
}

def load_words(dict_id='kaoyan'):
    """加载指定词库的单词"""
    if dict_id not in DICTIONARIES:
        return {'words': []}
    
    try:
        with open(DICTIONARIES[dict_id]['file'], 'r', encoding='utf-8') as f:
            # 将读取到的 JSON 数组封装到 'words' 键下
            data = json.load(f)
            return {'words': data}
    except FileNotFoundError:
        return {'words': []}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {DICTIONARIES[dict_id]['file']}")
        return {'words': []}

@app.route('/')
def root():
    return render_template('create_plan.html')

@app.route('/api/words')
def get_words():
    dict_id = request.args.get('dict', 'kaoyan')
    return jsonify(load_words(dict_id))

@app.route('/api/dictionaries')
def get_dictionaries():
    return jsonify(DICTIONARIES)

@app.route('/api/study-plans/current')
def get_current_plan():
    """获取当前进行中的学习计划"""
    session = Session()
    try:
        current_time = datetime.now()
        # 查找包含当前时间的学习计划
        plan = session.query(StudyPlan).filter(
            and_(
                StudyPlan.start_date <= current_time,
                StudyPlan.end_date >= current_time
            )
        ).first()
        
        if not plan:
            return jsonify({
                'status': 'no_plan',
                'message': '当前没有进行中的学习计划'
            })
            
        return jsonify({
            'status': 'success',
            'plan': {
                'id': plan.id,
                'exam_type': plan.exam_type,
                'start_date': plan.start_date.isoformat(),
                'end_date': plan.end_date.isoformat(),
                'total_words': plan.total_words,
                'daily_words': plan.daily_words,
                'created_at': plan.created_at.isoformat()
            }
        })
    finally:
        session.close()

@app.route('/api/study-plans/daily-tasks')
def get_daily_tasks():
    """获取今日的学习和复习任务"""
    session = Session()
    try:
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # 获取今日需要学习的单词
        new_words = session.query(WordPlan).filter(
            and_(
                WordPlan.first_learn_date >= today_start,
                WordPlan.first_learn_date <= today_end
            )
        ).all()
        
        # 获取今日需要复习的单词
        review_words = session.query(WordPlan).join(ReviewDate).filter(
            and_(
                ReviewDate.review_date >= today_start,
                ReviewDate.review_date <= today_end,
                ReviewDate.is_reviewed == False
            )
        ).all()
        
        return jsonify({
            'status': 'success',
            'tasks': {
                'new_words': [{
                    'id': word.id,
                    'word': word.word,
                    'phonetic': word.phonetic,
                    'meaning': word.meaning,
                    'example': word.example,
                    'is_learned': word.is_learned,
                    'is_mastered': word.is_mastered
                } for word in new_words],
                'review_words': [{
                    'id': word.id,
                    'word': word.word,
                    'phonetic': word.phonetic,
                    'meaning': word.meaning,
                    'example': word.example,
                    'is_learned': word.is_learned,
                    'is_mastered': word.is_mastered
                } for word in review_words]
            }
        })
    finally:
        session.close()

@app.route('/api/study-plans/mark-word', methods=['POST'])
def mark_word():
    """标记单词的学习状态"""
    session = Session()
    try:
        data = request.get_json()
        word_id = data.get('word_id')
        status = data.get('status')  # 'learned', 'mastered', 'reviewed'
        
        if not word_id or not status:
            return jsonify({
                'status': 'error',
                'message': '缺少必要参数'
            }), 400
            
        word = session.query(WordPlan).get(word_id)
        if not word:
            return jsonify({
                'status': 'error',
                'message': '单词不存在'
            }), 404
            
        if status == 'learned':
            word.is_learned = True
        elif status == 'mastered':
            word.is_mastered = True
        elif status == 'reviewed':
            # 标记今日的复习记录为已复习
            today = datetime.now().date()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())
            
            review = session.query(ReviewDate).filter(
                and_(
                    ReviewDate.word_plan_id == word_id,
                    ReviewDate.review_date >= today_start,
                    ReviewDate.review_date <= today_end
                )
            ).first()
            
            if review:
                review.is_reviewed = True
                
        session.commit()
        return jsonify({
            'status': 'success',
            'message': '状态更新成功'
        })
    except Exception as e:
        session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        session.close()

@app.route('/study-plan')
def study_plan():
    """学习计划页面"""
    return render_template('study_plan.html')

@app.route('/create-plan')
def create_plan():
    """创建学习计划页面"""
    return render_template('create_plan.html')

@app.route('/api/study-plans/create', methods=['POST'])
def create_study_plan():
    """创建新的学习计划"""
    try:
        data = request.get_json()
        user_input = data.get('user_input')
        
        if not user_input:
            return jsonify({
                'status': 'error',
                'message': '请输入学习需求'
            }), 400
            
        # 使用 WordPlanner 生成计划
        planner = WordPlanner()
        plan_data = planner.generate_plan(user_input)
        
        if not plan_data or 'status' not in plan_data or plan_data['status'] != 'success':
            return jsonify({
                'status': 'error',
                'message': '生成计划失败，请检查输入内容'
            }), 400
            
        # 返回计划预览信息
        return jsonify({
            'status': 'success',
            'plan': {
                'id': plan_data['plan_id'],
                'exam_type': plan_data['exam_type'],
                'start_date': plan_data['start_date'],
                'end_date': plan_data['end_date'],
                'total_words': plan_data['total_words'],
                'daily_words': plan_data['daily_words'],
                'daily_study_time': plan_data['daily_study_time']
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/study-plans/confirm', methods=['POST'])
def confirm_study_plan():
    """确认并激活学习计划"""
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')
        
        if not plan_id:
            return jsonify({
                'status': 'error',
                'message': '缺少计划ID'
            }), 400
            
        session = Session()
        try:
            # 检查计划是否存在
            plan = session.query(StudyPlan).get(plan_id)
            if not plan:
                return jsonify({
                    'status': 'error',
                    'message': '计划不存在'
                }), 404
                
            # 检查是否有其他进行中的计划
            current_time = datetime.now()
            active_plan = session.query(StudyPlan).filter(
                and_(
                    StudyPlan.start_date <= current_time,
                    StudyPlan.end_date >= current_time,
                    StudyPlan.id != plan_id
                )
            ).first()
            
            if active_plan:
                return jsonify({
                    'status': 'error',
                    'message': '已有进行中的学习计划，请先完成或取消当前计划'
                }), 400
                
            # 激活计划
            plan.start_date = datetime.now()
            session.commit()
            
            return jsonify({
                'status': 'success',
                'message': '计划已激活'
            })
        finally:
            session.close()
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 