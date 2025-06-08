// wrong_list.js

// 加载错题列表
async function loadWrongList(bookType) {
    const wrongList = document.getElementById('wrong-list');
    wrongList.innerHTML = '<li>加载中...</li>';
    try {
        const resp = await fetch(`/api/wrong_list?book=${bookType}`);
        if (resp.ok) {
            const data = await resp.json();
            if (data && data.length > 0) {
                wrongList.innerHTML = data.map(
                    (item, idx) => `<li class="p-2 bg-red-50 dark:bg-red-900/30 rounded">错题${idx+1}：${item.question} <span class=\"text-green-600 dark:text-green-400\">→ ${item.answer}</span></li>`
                ).join('');
            } else {
                wrongList.innerHTML = '<li>暂无错题</li>';
            }
        } else {
            wrongList.innerHTML = '<li>加载失败</li>';
        }
    } catch (e) {
        wrongList.innerHTML = '<li>网络错误</li>';
    }
}

// 显示/隐藏错题列表，并在显示时加载错题
function showWrongList(show) {
    const wrongListContainer = document.getElementById('wrong-list-container');
    if (wrongListContainer) {
        wrongListContainer.style.display = show ? 'block' : 'none';
        if (show) {
            const select = document.getElementById('error-book-select');
            if (select) loadWrongList(select.value);
        }
    }
}

// 页面加载时初始化错题本选择监听
window.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('app-mode-select');
    if (select) {
        // 设置初始值
        const mode = localStorage.getItem('appMode') || 'scene_chat';
        select.value = mode;

        // 根据初始值显示/隐藏错题列表
        if (mode === 'wrong') {
            showWrongList(true);
        } else {
            showWrongList(false);
        }

        // 监听模式变化
        select.addEventListener('change', function() {
            localStorage.setItem('appMode', this.value);
            if (this.value === 'wrong') {
                showWrongList(true);
            } else {
                showWrongList(false);
            }
        });
    }

    // 新增：监听"确定"按钮
    const filterBtn = document.getElementById('filter-confirm-btn');
    const bookSelect = document.getElementById('error-book-select');
    if (filterBtn && bookSelect) {
        filterBtn.addEventListener('click', function() {
            loadWrongList(bookSelect.value);
        });
    }
}); 