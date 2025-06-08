let currentPlan = null;

async function handleSubmit(event) {
    event.preventDefault();
    
    const userInput = document.getElementById('userInput').value.trim();
    if (!userInput) {
        showToast('请输入学习需求', 'warning');
        return false;
    }

    // 显示加载提示或禁用按钮
    const createButton = document.querySelector('#planForm button[type="submit"]');
    createButton.disabled = true;
    createButton.textContent = '生成中...';
    
    try {
        const response = await fetch('/api/study-plans/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ user_input: userInput })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            currentPlan = data.plan;
            showPlanPreview(data.plan);
        } else {
            showToast(data.message || '生成计划失败', 'error');
        }
    } catch (error) {
        console.error('创建计划失败:', error);
        showToast('创建计划失败，请重试', 'error');
    } finally {
        // 恢复按钮状态
        createButton.disabled = false;
        createButton.textContent = '生成学习计划';
    }

    return false;
}

function showPlanPreview(plan) {
    const previewHtml = `
        <h3>学习计划预览</h3>
        <div class="preview-content">
            <div class="alert alert-info">
                <p><strong>考试类型：</strong>${plan.exam_type}</p>
                <p><strong>考试日期：</strong>${formatDate(plan.exam_date)}</p>
                <p><strong>总单词数：</strong>${plan.total_words}</p>
                <p><strong>每日新学单词数：</strong>${plan.daily_words}</p>
                <p><strong>计划开始日期：</strong>${formatDate(plan.start_date)}</p>
                <p><strong>计划结束日期：</strong>${formatDate(plan.end_date)}</p>
                <p><strong>预计每日学习时间：</strong>${plan.daily_study_time} 分钟</p>
            </div>
            <div class="alert alert-warning">
                <h6>学习计划说明：</h6>
                <ul>
                    <li>系统会根据艾宾浩斯记忆曲线自动安排复习时间</li>
                    <li>每天的学习任务包括新单词和需要复习的单词</li>
                    <li>您可以根据实际情况调整学习进度</li>
                </ul>
            </div>
        </div>
        <div class="preview-actions">
            <button onclick="resetForm()" class="btn btn-secondary">重新创建</button>
            <button onclick="confirmPlan()" class="btn btn-primary">确认开始学习</button>
        </div>
    `;
    
    document.getElementById('planPreview').innerHTML = previewHtml;
    document.getElementById('planForm').style.display = 'none';
    document.getElementById('planPreview').style.display = 'block';
}

function resetForm() {
    document.getElementById('planForm').reset();
    document.getElementById('planForm').style.display = 'block';
    document.getElementById('planPreview').style.display = 'none';
    currentPlan = null;
}

async function confirmPlan() {
    if (!currentPlan) {
        showToast('没有可确认的计划', 'warning');
        return;
    }

    // 显示加载提示或禁用按钮
    const confirmButton = document.querySelector('#planPreview .btn-primary');
    confirmButton.disabled = true;
    confirmButton.textContent = '确认中...';

    try {
        const response = await fetch('/api/study-plans/confirm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ plan_id: currentPlan.id })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            showToast('计划创建成功，即将开始学习', 'success');
            setTimeout(() => {
                window.location.href = '/study-plan';
            }, 1500);
        } else {
            showToast(data.message || '确认计划失败', 'error');
        }
    } catch (error) {
        console.error('确认计划失败:', error);
        showToast('确认计划失败，请重试', 'error');
    } finally {
         // 恢复按钮状态 (如果跳转失败)
         confirmButton.disabled = false;
         confirmButton.textContent = '确认开始学习';
    }
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function showToast(message, type = 'info') {
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
    
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    container.appendChild(toast);
    document.body.appendChild(container);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => {
        container.remove();
    });
} 