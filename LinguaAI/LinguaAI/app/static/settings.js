function toggleSystemPrompt() {
    const container = document.getElementById('system-prompt-container');
    const chevron = document.getElementById('system-prompt-chevron');
    
    // Toggle the collapsed state with a smoother height transition
    if (!container.style.maxHeight || container.style.maxHeight === '0px') {
        container.style.maxHeight = container.scrollHeight + 'px';
        container.classList.remove('opacity-0');
        chevron.classList.add('rotate-180');
    } else {
        container.style.maxHeight = '0px';
        container.classList.add('opacity-0');
        chevron.classList.remove('rotate-180');
    }
    
    // Save preference to localStorage
    localStorage.setItem('systemPromptCollapsed', container.style.maxHeight === '0px');
}

// Set initial state on page load
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('system-prompt-container');
    const chevron = document.getElementById('system-prompt-chevron');
    const isCollapsed = localStorage.getItem('systemPromptCollapsed') === 'true';
    
    if (isCollapsed) {
        container.style.maxHeight = '0px';
        container.classList.add('opacity-0');
    } else {
        container.style.maxHeight = container.scrollHeight + 'px';
        chevron.classList.add('rotate-180');
    }
}, { once: true });

// 打开设置模态框
function openSettingsModal() {
    const modal = document.getElementById('settings-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

// 关闭设置模态框
function closeSettingsModal() {
    const modal = document.getElementById('settings-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

// 切换设置标签页
function switchSettingsTab(tabName) {
    // 更新标签页样式
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.classList.remove('active', 'text-blue-600', 'dark:text-blue-400', 'border-b-2', 'border-blue-600', 'dark:border-blue-400');
        tab.classList.add('text-gray-600', 'dark:text-gray-400');
    });
    const activeTab = document.querySelector(`[onclick="switchSettingsTab('${tabName}')"]`);
    activeTab.classList.add('active', 'text-blue-600', 'dark:text-blue-400', 'border-b-2', 'border-blue-600', 'dark:border-blue-400');
    activeTab.classList.remove('text-gray-600', 'dark:text-gray-400');

    // 更新面板显示
    document.querySelectorAll('.settings-panel').forEach(panel => {
        panel.classList.add('hidden');
    });
    document.getElementById(`${tabName}-settings`).classList.remove('hidden');
}

// 更新字体大小
function updateFontSize(size) {
    document.documentElement.style.fontSize = `${size}px`;
    localStorage.setItem('fontSize', size);
}

// 初始化设置
document.addEventListener('DOMContentLoaded', () => {
    // 恢复保存的字体大小
    const savedFontSize = localStorage.getItem('fontSize');
    if (savedFontSize) {
        document.documentElement.style.fontSize = `${savedFontSize}px`;
        document.querySelector('input[type="range"]').value = savedFontSize;
    }

    // 设置按钮点击事件
    document.getElementById('settings-button').addEventListener('click', openSettingsModal);

    // 点击模态框外部关闭
    document.getElementById('settings-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            closeSettingsModal();
        }
    });
});

// 保存设置
function saveSettings() {
    try {
        // 获取所有设置值
        const settings = {
            apiHost: document.getElementById('api-host')?.value || '',
            apiKey: document.getElementById('api-key')?.value || '',
            tavilyApiKey: document.getElementById('tavily-api-key')?.value || '',
            modelName: document.getElementById('model-name')?.value || '',
            temperature: document.getElementById('temperature')?.value || '1.0',
            topP: document.getElementById('top-p')?.value || '0.95',
            maxTokens: document.getElementById('max-tokens')?.value || '',
            configName: document.getElementById('config-name')?.value || ''
        };

        // 保存到localStorage
        localStorage.setItem('modelSettings', JSON.stringify(settings));
        
        // 隐藏警告
        const warningElement = document.getElementById('settings-warning');
        if (warningElement) {
            warningElement.classList.add('hidden');
        }
        
        // 显示保存成功提示
        alert('设置已保存');
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('保存设置时出错，请重试');
    }
}

// 加载设置
function loadSettings() {
    try {
        const savedSettings = localStorage.getItem('modelSettings');
        if (savedSettings) {
            const settings = JSON.parse(savedSettings);
            
            // 使用可选链操作符和空值合并操作符
            const elements = {
                'api-host': settings.apiHost || '',
                'api-key': settings.apiKey || '',
                'tavily-api-key': settings.tavilyApiKey || '',
                'model-name': settings.modelName || '',
                'temperature': settings.temperature || '1.0',
                'top-p': settings.topP || '0.95',
                'max-tokens': settings.maxTokens || '',
                'config-name': settings.configName || ''
            };

            // 更新所有输入值
            Object.entries(elements).forEach(([id, value]) => {
                const element = document.getElementById(id);
                if (element) {
                    element.value = value;
                }
            });
            
            // 更新显示值
            const tempValue = document.getElementById('temperature-value');
            const topPValue = document.getElementById('top-p-value');
            if (tempValue) tempValue.textContent = settings.temperature || '1.0';
            if (topPValue) topPValue.textContent = settings.topP || '0.95';
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// 监听设置变化
function watchSettingsChanges() {
    const inputs = document.querySelectorAll('#model-settings input, #model-settings select');
    inputs.forEach(input => {
        input.addEventListener('change', () => {
            const warningElement = document.getElementById('settings-warning');
            if (warningElement) {
                warningElement.classList.remove('hidden');
            }
        });
    });
}

// 创建新配置
function createNewSettingsConfig() {
    try {
        // 清空所有输入
        const elements = {
            'api-host': '',
            'api-key': '',
            'tavily-api-key': '',
            'model-name': '',
            'temperature': '1.0',
            'top-p': '0.95',
            'max-tokens': '',
            'config-name': ''
        };

        // 更新所有输入值
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.value = value;
            }
        });
        
        // 更新显示值
        const tempValue = document.getElementById('temperature-value');
        const topPValue = document.getElementById('top-p-value');
        if (tempValue) tempValue.textContent = '1.0';
        if (topPValue) topPValue.textContent = '0.95';
        
        // 显示警告
        const warningElement = document.getElementById('settings-warning');
        if (warningElement) {
            warningElement.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error creating new config:', error);
        alert('创建新配置时出错，请重试');
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    try {
        loadSettings();
        watchSettingsChanges();
    } catch (error) {
        console.error('Error initializing settings:', error);
    }
});