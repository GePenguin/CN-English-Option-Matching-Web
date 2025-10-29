from flask import Flask, render_template, request, redirect, url_for, session
import requests
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 替换为您的密钥

# 加载词库 - 优化版
def load_common_words():
    with open('common_words.txt', encoding='utf-8') as f:
        lines = f.read().splitlines()
        categories = {}  # 按首字母分类
        
        for line in lines:
            if not line.strip() or len(line.split()) < 2:
                continue
                
            parts = line.split(' ', 1)
            word = parts[0]
            definition = parts[1]
            
            # 提取词性
            pos = definition.split('.', 1)[0].strip()
            meaning = definition.split('.', 1)[1].strip() if '.' in definition else definition
            
            # 创建新类别如果不存在
            first_char = word[0].upper()
            if first_char not in categories:
                categories[first_char] = []
                
            categories[first_char].append({
                'word': word,
                'pos': pos,
                'local_meaning': meaning
            })
    return categories

WORD_CATEGORIES = load_common_words()

# 统计信息
stats = {
    'total_questions': 0,
    'correct_answers': 0,
    'current_streak': 0
}

def get_random_word_data():
    """获取随机单词数据"""
    # 随机选择一个类别
    category = random.choice(list(WORD_CATEGORIES.values()))
    word_entry = random.choice(category)
    
    base_word = word_entry['word']
    
    return {
        **word_entry
    }

def get_options(correct_word_obj, include_correct=True):
    """生成选项，有50%概率不包含正确答案"""
    correct_word = correct_word_obj['word']
    
    # 从同类别中获取干扰项
    same_cat = []
    for cat in WORD_CATEGORIES.values():
        if any(w['word'] == correct_word for w in cat):
            same_cat = [w for w in cat if w['word'] != correct_word]
            break
    
    # 获取干扰项
    all_distractors = []
    # 先尝试从同类别中获取
    if same_cat:
        all_distractors.extend(same_cat)
    
    # 如果同类别干扰项不足，从其他类别补充
    if len(all_distractors) < 5:  # 确保有足够干扰项
        for cat in WORD_CATEGORIES.values():
            # 排除当前类别，避免重复
            if same_cat and cat == same_cat:
                continue
            all_distractors.extend(cat)
            if len(all_distractors) >= 30:  # 足够干扰项数量
                break
    
    # 去重并排除正确答案
    unique_distractors = []
    seen = set()
    for word in all_distractors:
        if word['word'] not in seen and word['word'] != correct_word:
            seen.add(word['word'])
            unique_distractors.append(word)
    
    # 确保格式一致
    options = []
    
    # 如果包含正确答案，则添加 + 3干扰项
    if include_correct:
        options.append({
            'word': correct_word,
            'pos': correct_word_obj['pos']
        })
        # 随机选择3个干扰项
        distractors = random.sample(unique_distractors, min(3, len(unique_distractors)))
        for d in distractors:
            options.append({
                'word': d['word'],
                'pos': d.get('pos', '?')
            })
    else:
        # 不包含正确答案，使用4个干扰项
        distractors = random.sample(unique_distractors, min(4, len(unique_distractors)))
        for d in distractors:
            options.append({
                'word': d['word'],
                'pos': d.get('pos', '?')
            })
    
    random.shuffle(options)
    return options, include_correct

@app.route('/', methods=['GET', 'POST'])
def index():
    stats = session.get('stats', {
        'total_questions': 0,
        'correct_answers': 0,
        'current_streak': 0
    })

    # POST 请求
    if request.method == 'POST':
        selected_word = request.form.get('word')
        user_input = request.form.get('user_input', '').strip()
        correct_word = request.form.get('correct_word')
        pos = request.form.get('pos')
        
        # 统一处理用户答案
        user_answer = selected_word if selected_word else user_input
        
        # 更新统计
        stats['total_questions'] += 1
        is_correct = user_answer.lower() == correct_word.lower() if user_answer else False
        
        if is_correct:
            stats['correct_answers'] += 1
            stats['current_streak'] += 1
        else:
            stats['current_streak'] = 0
            
        session['stats'] = stats
        
        # 获取正确答案数据
        correct_word_obj = None
        for cat in WORD_CATEGORIES.values():
            for word in cat:
                if word['word'] == correct_word:
                    correct_word_obj = word
                    break
            if correct_word_obj:
                break
        
        # 结果数据
        result_data = {
            'is_correct': is_correct,
            'user_input': user_input if not selected_word else "",
            'selected_word': selected_word if not user_input else "",
            'correct_word': correct_word,
            'phonetic': '',
            'definition': correct_word_obj.get('local_meaning', '') if correct_word_obj else '',
            'example': '',
            'pos': pos,
            'stats': {
                'accuracy': int(stats['correct_answers'] * 100 / stats['total_questions']) if stats['total_questions'] > 0 else 100,
                'streak': stats['current_streak']
            }
        }
        
        return render_template('result.html', **result_data)
    # GET请求，获取新问题
    # GET请求，获取新问题
    question_obj = get_random_word_data()
    if not question_obj:
        return redirect(url_for('error'))
    
    # 有50%的概率选项中不包含正确答案
    include_correct = random.choice([True, False])
    options, include_correct = get_options(question_obj, include_correct=include_correct)
    
    # 使用本地词库中提供的释义作为问题
    question_text = f"{question_obj['local_meaning']}"
    
    return render_template('index.html', 
                          question=question_text,
                          word=question_obj['word'],
                          options=options,
                          include_correct=include_correct,
                          total_options=len(options),  # 新增选项数量
                          correct_word=question_obj['word'],
                          pos=question_obj['pos'],
                          stats=session.get('stats', stats))

@app.route('/reset')
def reset():
    """重置统计数据"""
    session['stats'] = {
        'total_questions': 0,
        'correct_answers': 0,
        'current_streak': 0
    }
    return redirect(url_for('index'))

@app.route('/error')
def error():
    return render_template('error.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5246, debug=True)
