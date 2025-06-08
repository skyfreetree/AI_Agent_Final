let words = [];
let currentIndex = 0;
let unknownWords = []; // 生词本列表

// 获取DOM元素
const wordElement = document.getElementById('current-word');
const phoneticElement = document.getElementById('phonetic');
const meaningElement = document.getElementById('meaning');
const exampleElement = document.getElementById('example');
const progressElement = document.getElementById('progress');
const dictionarySelect = document.getElementById('dictionary');
const practiceArea = document.getElementById('practice-area'); // 练习区域
const unknownWordsArea = document.getElementById('unknown-words-area'); // 生词本区域
const unknownWordsList = document.getElementById('unknown-words-list'); // 生词本列表
const unknownWordsBtn = document.getElementById('unknown-words-btn'); // 生词本按钮
const unknownWordsCount = document.getElementById('unknown-words-count'); // 生词本数量显示
const backToPracticeBtn = document.getElementById('back-to-practice-btn'); // 返回按钮

// 新增的按钮元素
const easyBtn = document.getElementById('easy-btn');
const fuzzyBtn = document.getElementById('fuzzy-btn');
const unknownBtn = document.getElementById('unknown-btn');

// 加载单词数据
async function loadWords() {
    try {
        const dictId = dictionarySelect.value;
        const response = await fetch(`/api/words?dict=${dictId}`);
        const data = await response.json();
        
        if (data && data.words && Array.isArray(data.words)) {
            // 转换词库数据格式以匹配前端期望的字段名
            words = data.words.map(item => ({
                word: item.name || item.word || '', 
                phonetic: item.usphone || item.ukphone || '', 
                meaning: Array.isArray(item.trans) ? item.trans.join('; ') : '',
                example: '' 
            }));

            currentIndex = 0; // Reset index when loading new dictionary
            updateProgress();
            showCurrentWord();
            // 确保按钮可用
            easyBtn.disabled = false;
            fuzzyBtn.disabled = false;
            unknownBtn.disabled = false;
            updateUnknownWordsCount(); // 更新生词本数量显示
        } else {
            console.error('Invalid data format received or empty dictionary:', data);
            words = []; // Clear words on error or invalid data
            currentIndex = 0;
            updateProgress();
            // 禁用按钮并显示提示
            wordElement.textContent = '加载失败或词库为空';
            phoneticElement.textContent = '';
            meaningElement.textContent = '';
            exampleElement.textContent = '';
            easyBtn.disabled = true;
            fuzzyBtn.disabled = true;
            unknownBtn.disabled = true;
            updateUnknownWordsCount(); // 更新生词本数量显示
        }

    } catch (error) {
        console.error('Error loading words:', error);
        words = []; // Clear words on error
        currentIndex = 0;
        updateProgress();
        // 禁用按钮并显示错误信息
        wordElement.textContent = '加载失败';
        phoneticElement.textContent = '';
        meaningElement.textContent = '';
        exampleElement.textContent = '';
        easyBtn.disabled = true;
        fuzzyBtn.disabled = true;
        unknownBtn.disabled = true;
        updateUnknownWordsCount(); // 更新生词本数量显示
    }
}

// 显示当前单词
function showCurrentWord() {
    if (words.length === 0) {
        wordElement.textContent = '当前词库没有单词';
        phoneticElement.textContent = '';
        meaningElement.textContent = '';
        exampleElement.textContent = '';
        easyBtn.disabled = true;
        fuzzyBtn.disabled = true;
        unknownBtn.disabled = true;
        return;
    }
    
    const currentWord = words[currentIndex];
    wordElement.textContent = currentWord.word || '';
    phoneticElement.textContent = currentWord.phonetic || '';
    meaningElement.textContent = currentWord.meaning || '';
    exampleElement.textContent = currentWord.example || '';
}

// 更新进度
function updateProgress() {
    if (words.length === 0) {
        progressElement.textContent = '0/0';
    } else {
        progressElement.textContent = `${currentIndex + 1}/${words.length}`;
    }
}

// 更新生词本数量显示
function updateUnknownWordsCount() {
    unknownWordsCount.textContent = unknownWords.length;
}

// 处理用户反馈：简单
function handleEasy() {
    if (words.length === 0) return;
    nextWord();
}

// 处理用户反馈：模糊
function handleFuzzy() {
    if (words.length === 0) return;
    const currentWord = words[currentIndex];
    // 将当前单词插入到列表的稍后位置 (例如当前位置 + 5) 
    const insertIndex = Math.min(currentIndex + 5, words.length);
    words.splice(insertIndex, 0, currentWord);
    nextWord();
}

// 处理用户反馈：不认识
function handleUnknown() {
    if (words.length === 0) return;
    const currentWord = words[currentIndex];
    // 添加到生词本 (避免重复添加)
    if (!unknownWords.some(word => word.word === currentWord.word)) {
        unknownWords.push(currentWord);
        console.log('生词本:', unknownWords);
        updateUnknownWordsCount(); // 更新生词本数量显示
    }
    nextWord();
}

// 下一个单词
function nextWord() {
    if (words.length === 0) return;

    currentIndex++;
    // 如果到达列表末尾，循环回开头
    if (currentIndex >= words.length) {
        currentIndex = 0;
        // 可选：在这里处理生词本或完成词库的逻辑
        console.log('完成当前词库一轮练习');
    }

    updateProgress();
    showCurrentWord();
}

// 显示生词本
function showUnknownWords() {
    practiceArea.classList.add('hidden');
    unknownWordsArea.classList.remove('hidden');
    renderUnknownWordsList();
}

// 渲染生词本列表
function renderUnknownWordsList() {
    unknownWordsList.innerHTML = ''; // 清空现有列表
    if (unknownWords.length === 0) {
        const listItem = document.createElement('li');
        listItem.textContent = '生词本是空的。';
        unknownWordsList.appendChild(listItem);
        return;
    }
    unknownWords.forEach((word, index) => {
        const listItem = document.createElement('li');
        listItem.innerHTML = `<strong>${word.word}</strong> ${word.phonetic ? `[${word.phonetic}]` : ''} - ${word.meaning || ''}`;
        
        // 添加"我记住了"按钮
        const learnedButton = document.createElement('button');
        learnedButton.textContent = '我记住了';
        learnedButton.classList.add('btn-learned');
        learnedButton.dataset.index = index; // 存储单词在 unknownWords 数组中的索引
        
        // 添加点击事件监听器
        learnedButton.addEventListener('click', handleLearned);

        listItem.appendChild(learnedButton);
        unknownWordsList.appendChild(listItem);
    });
}

// 处理用户标记为"我记住了"
function handleLearned(event) {
    // 获取点击按钮对应的单词在 unknownWords 数组中的索引
    const indexToRemove = parseInt(event.target.dataset.index);
    
    // 从 unknownWords 数组中移除该单词
    unknownWords.splice(indexToRemove, 1);
    
    // 重新渲染生词本列表和更新数量显示
    renderUnknownWordsList();
    updateUnknownWordsCount();
}

// 返回练习界面
function backToPractice() {
    unknownWordsArea.classList.add('hidden');
    practiceArea.classList.remove('hidden');
    showCurrentWord(); // 返回时显示当前单词
}

// 事件监听
document.addEventListener('DOMContentLoaded', () => {
    // 添加新的按钮事件监听
    easyBtn.addEventListener('click', handleEasy);
    fuzzyBtn.addEventListener('click', handleFuzzy);
    unknownBtn.addEventListener('click', handleUnknown);

    // 词库切换事件
    dictionarySelect.addEventListener('change', loadWords);

    // 生词本按钮事件
    unknownWordsBtn.addEventListener('click', showUnknownWords);

    // 返回按钮事件
    backToPracticeBtn.addEventListener('click', backToPractice);

    // 初始化加载默认词库
    loadWords();
}); 