// 全局变量
let currentWordId = null;
const wordCardModal = new bootstrap.Modal(document.getElementById('wordCardModal'));

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 加载当前计划
    loadCurrentPlan();
    // 加载今日任务
    loadDailyTasks();
});

// 加载当前学习计划
async function loadCurrentPlan() {
    try {
        const response = await fetch('/api/study-plans/current');
        const data = await response.json();
        
        if (data.status === 'no_plan') {
            document.getElementById('no-plan-message').style.display = 'block';
            document.getElementById('plan-info').style.display = 'none';
        } else {
            document.getElementById('no-plan-message').style.display = 'none';
            document.getElementById('plan-info').style.display = 'block';
            
            // 更新计划信息
            const plan = data.plan;
            document.getElementById('exam-type').textContent = plan.exam_type;
            document.getElementById('start-date').textContent = formatDate(plan.start_date);
            document.getElementById('end-date').textContent = formatDate(plan.end_date);
            document.getElementById('total-words').textContent = plan.total_words;
            document.getElementById('daily-words').textContent = plan.daily_words;
            document.getElementById('created-at').textContent = formatDate(plan.created_at);
        }
    } catch (error) {
        console.error('加载学习计划失败:', error);
        showToast('加载学习计划失败，请刷新页面重试', 'error');
    }
}

// 加载今日学习任务
async function loadDailyTasks() {
    try {
        const response = await fetch('/api/study-plans/daily-tasks');
        const data = await response.json();
        
        if (data.status === 'success') {
            const tasks = data.tasks;
            
            // 更新新单词列表
            updateWordList('new-words-list', tasks.new_words, '新单词');
            document.getElementById('new-words-count').textContent = tasks.new_words.length;
            
            // 更新复习单词列表
            updateWordList('review-words-list', tasks.review_words, '复习单词');
            document.getElementById('review-words-count').textContent = tasks.review_words.length;
        }
    } catch (error) {
        console.error('加载今日任务失败:', error);
        showToast('加载今日任务失败，请刷新页面重试', 'error');
    }
}

// 更新单词列表
function updateWordList(containerId, words, type) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    if (words.length === 0) {
        container.innerHTML = `<div class="alert alert-info">今日没有${type}任务</div>`;
        return;
    }
    
    words.forEach(word => {
        const wordCard = createWordCard(word, type);
        container.appendChild(wordCard);
    });
}

// 创建单词卡片
function createWordCard(word, type) {
    const card = document.createElement('div');
    card.className = 'word-card';
    card.innerHTML = `
        <div class="word-header">
            <h2>${word.word}</h2>
            <span class="phonetic">${word.phonetic || ''}</span>
        </div>
        <div class="word-content">
            <p><strong>释义：</strong>${word.meaning || '暂无释义'}</p>
            ${word.example ? `<p><strong>例句：</strong>${word.example}</p>` : ''}
        </div>
        <div class="word-status">
            ${getStatusBadge(word)}
        </div>
    `;
    
    // 点击卡片显示详情
    card.addEventListener('click', () => showWordDetail(word, type));
    
    return card;
}

// 获取状态标签
function getStatusBadge(word) {
    if (word.is_mastered) {
        return '<span class="badge bg-success">很熟练</span>';
    } else if (word.is_learned) {
        return '<span class="badge bg-warning">模糊</span>';
    } else {
        return '<span class="badge bg-danger">不认识</span>';
    }
}

// 显示单词详情
function showWordDetail(word, type) {
    currentWordId = word.id;
    
    // 更新模态框内容
    document.getElementById('wordCardTitle').textContent = type;
    document.getElementById('modal-word').textContent = word.word;
    document.getElementById('modal-phonetic').textContent = word.phonetic || '';
    document.getElementById('modal-meaning').textContent = word.meaning || '暂无释义';
    document.getElementById('modal-example').textContent = word.example || '暂无例句';
    
    // 显示模态框
    wordCardModal.show();
}

// 标记单词状态
async function markWordStatus(status) {
    if (!currentWordId) return;
    
    try {
        const response = await fetch('/api/study-plans/mark-word', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                word_id: currentWordId,
                status: status
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showToast('状态更新成功', 'success');
            // 重新加载任务列表
            loadDailyTasks();
            // 关闭模态框
            wordCardModal.hide();
        } else {
            showToast(data.message || '状态更新失败', 'error');
        }
    } catch (error) {
        console.error('更新单词状态失败:', error);
        showToast('更新单词状态失败，请重试', 'error');
    }
}

// 格式化日期
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// 显示提示消息
function showToast(message, type = 'info') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    // 添加到页面
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    container.appendChild(toast);
    document.body.appendChild(container);
    
    // 显示toast
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // 自动移除
    toast.addEventListener('hidden.bs.toast', () => {
        container.remove();
    });
} 