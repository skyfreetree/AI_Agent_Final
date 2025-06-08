// Global state management
const state = {
    ws: null,
    isInitializingSettings: false,
    currentSettings: null,
    originalSettings: null,
    isScrolledManually: false,
    lastScrollTop: 0,
    currentAssistantMessage: null,
    currentConversationId: null,
    isLoading: false,
    editingMessageId: null,
    abortController: null,
    mode: 'scene_chat',
    clientId: crypto.randomUUID() // Generate unique client ID
};
function updateMainContentVisibility() {
    const chatInputWrapper = document.getElementById('chat-input-wrapper');
    const chatMessagesWrapper = document.getElementById('chat-messages-wrapper');
    const wrongListContainer = document.getElementById('wrong-list-container');
    const studySummaryContainer = document.getElementById('study-status');
    if (state.mode === 'wrong') {
        chatInputWrapper.style.display = 'none';
        chatMessagesWrapper.style.display = 'none';
        wrongListContainer.style.display = '';
        studySummaryContainer.style.display = 'none';
    } else if (state.mode === 'study_summary') {
        chatInputWrapper.style.display = 'none';
        wrongListContainer.style.display = 'none';
        studySummaryContainer.style.display = 'block';
        chatMessagesWrapper.style.display = 'none';
        setTimeout(() => {
            loadStudyStatus();
        }, 100);
    } else {
        chatInputWrapper.style.display = '';
        chatMessagesWrapper.style.display = '';
        wrongListContainer.style.display = 'none';
        studySummaryContainer.style.display = 'none';
    }
}
function switchMode(mode) {
    state.mode = mode;
    updateMainContentVisibility();
    loadConversations();
    updateNewActionBtnLabel();
    updateConversationListTitle();
    startNewConversation();
}
document.addEventListener('DOMContentLoaded', () => {
    updateMainContentVisibility();
    updateNewActionBtnLabel();
    updateConversationListTitle();
});
function updateNewActionBtnLabel() {
    const label = document.getElementById('new-action-btn-label');
    if (!label) return;
    if (state.mode === 'scene_chat') {
        label.textContent = '新对话';
    } else if (state.mode === 'task_chat') {
        label.textContent = '新任务';
    } else {
        label.textContent = '';
    }
}
function updateConversationListTitle() {
    const title = document.getElementById('conversation-list-title');
    if (!title) return;
    if (state.mode === 'scene_chat') {
        title.textContent = '对话';
    } else if (state.mode === 'task_chat') {
        title.textContent = '任务';
    } else {
        title.textContent = '对话';
    }
}
// 放大图片预览弹窗
function showImagePreview(src, alt) {
    let modal = document.getElementById('image-preview-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'image-preview-modal';
        modal.style.position = 'fixed';
        modal.style.top = 0;
        modal.style.left = 0;
        modal.style.width = '100vw';
        modal.style.height = '100vh';
        modal.style.background = 'rgba(0,0,0,0.8)';
        modal.style.display = 'flex';
        modal.style.alignItems = 'center';
        modal.style.justifyContent = 'center';
        modal.style.zIndex = 9999;
        modal.innerHTML = `
            <div style="position:relative;max-width:90vw;max-height:90vh;">
                <img id="image-preview-img" src="" alt="" style="max-width:90vw;max-height:90vh;border-radius:8px;box-shadow:0 2px 16px #0008;" />
                <button id="close-image-preview" style="position:absolute;top:8px;right:8px;background:#fff;border:none;border-radius:50%;width:32px;height:32px;font-size:20px;cursor:pointer;">×</button>
            </div>
        `;
        document.body.appendChild(modal);
        modal.addEventListener('click', function(e) {
            if (e.target === modal || e.target.id === 'close-image-preview') {
                modal.style.display = 'none';
            }
        });
    }
    const img = document.getElementById('image-preview-img');
    img.src = src;
    img.alt = alt || '';
    modal.style.display = 'flex';
}

// DOM Elements
const elements = {
    chatForm: document.getElementById('chat-form'),
    messageInput: document.getElementById('message-input'),
    chatMessages: document.getElementById('chat-messages'),
    jumpToBottomButton: document.getElementById('jump-to-bottom'),
    fileInput: document.getElementById('file-input'),
    filePreviewContainer: document.getElementById('file-preview-container'),
    sendButton: document.getElementById('send-button'),
    stopButton: document.getElementById('stop-button')
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeCore();
    initializeEventListeners();
}, { once: true });

function initializeCore() {
    loadConversations();
    startNewConversation();
    connectWebSocket();
    initializeSettings();
}

function initializeEventListeners() {
    elements.chatMessages.addEventListener('scroll', handleScroll);
    document.getElementById('new-conversation-btn')?.addEventListener('click', startNewConversation);
    
    // Handle visibility change
    document.addEventListener('visibilitychange', handleVisibilityChange);
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()} ${date.toLocaleTimeString()}`;
}

function scrollToBottom() {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    state.isScrolledManually = false;
    elements.jumpToBottomButton.classList.remove('visible');
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => showCopiedFeedback(event.target))
        .catch(err => console.error('Failed to copy:', err));
}

function showCopiedFeedback(button) {
    const originalText = button.textContent;
    button.textContent = 'Copied!';
    setTimeout(() => {
        button.textContent = originalText;
    }, 2000);
}

// Error handling
function handleError(error, context) {
    console.error(`Error in ${context}:`, error);
    // You could add more sophisticated error handling here
}

function connectWebSocket() {
    // Use secure WebSocket if the page is served over HTTPS
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${state.clientId}`;
    
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('WebSocket connected');
    };

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    state.ws.onclose = () => {
        // Reconnect after a delay
        setTimeout(connectWebSocket, 3000);
    };

    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'conversation_created':
        case 'conversation_deleted':
        case 'message_added':
            // Always update the conversations list to reflect changes
            loadConversations();
            
            // Additional handling for current conversation
            if (data.type === 'message_added' && state.currentConversationId === data.conversation_id) {
                // loadConversation(data.conversation_id);
                // 直接追加新消息gkq
                appendMessage(data.message);
            } else if (data.type === 'conversation_deleted' && state.currentConversationId === data.conversation_id) {
                startNewConversation();
            }
            break;
        
        case 'message_edited':
            // Find the message element by its ID
            const messageDiv = document.querySelector(`[data-message-id="${data.message_id}"]`);
            if (messageDiv) {
                if (data.role === 'assistant') {
                    // For assistant messages, use the markdown renderer
                    updateAssistantMessage(data.content, messageDiv);
                } else {
                    // For user messages, just update the text content
                    messageDiv.textContent = data.content;
                    // Re-add edit button
                    addEditButton(messageDiv, data.message_id, data.content);
                }
            }
            break;
            
        case 'summary_updated':
            // Find and update the specific conversation's summary
            const conversationElement = document.querySelector(`[data-conversation-id="${data.conversation_id}"]`);
            if (conversationElement) {
                const summaryElement = conversationElement.querySelector('.text-\\[10px\\].text-gray-500');
                if (summaryElement) {
                    summaryElement.textContent = data.summary || 'No summary';
                }
            }
            break;
    }
}

// New helper function to find message div
function findMessageById(messageId) {
    // For now, we'll find the message by its content position
    // In a future update, we should add message IDs to the divs
    return null; // TODO: Implement message finding logic
}

function addEditButton(messageDiv, messageId, content) {
    const editButton = document.createElement('button');
    // editButton.className = 'absolute top-0 right-2 p-1 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200';
    editButton.className = 'edit-button';
    editButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
    `;
    editButton.onclick = () => openEditModal(messageDiv, messageId, content);
    messageDiv.appendChild(editButton);
}
function addAudioButton(messageDiv, messageId, content) {
    const audioButton = document.createElement('button');
    // audioButton.className = 'absolute top-2 right-0 p-1 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200';
    audioButton.className = 'audio-button';
    audioButton.innerHTML = `
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5l-7 7 7 7V5zM19 5v14a2 2 0 01-2 2h-2a2 2 0 01-2-2V5a2 2 0 012-2h2a2 2 0 012 2z" />
    </svg>
    `;
    audioButton.onclick = () => output_audio(messageDiv, messageId, content);
    messageDiv.appendChild(audioButton);
}
async function output_audio(messageDiv, messageId, content) {
    try {
        console.log('audio content', content);
        console.log('audio message', messageDiv.textContent);
        const formData = new FormData();
        formData.append('text', content);

        const response = await fetch('/text_to_speech', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to generate audio');
        }

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.play();
    } catch (error) {
        console.error('Error generating audio:', error);
    }
}


document.addEventListener('DOMContentLoaded', () => {
    loadConversations();
    startNewConversation();
    connectWebSocket(); // Replace startPolling() with WebSocket connection
    initializeSettings(); // Changed from loadSettings
    
    // Add new conversation button event listener here
    document.getElementById('new-conversation-btn')?.addEventListener('click', startNewConversation);
    
    // Initialize scroll handling
    elements.chatMessages.addEventListener('scroll', handleScroll);
    handleScroll(); // Check initial scroll position
}, { once: true });

document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Optional: You could close the WebSocket here if desired
    } else {
        // Ensure we have a connection when page becomes visible
        if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
        loadConversations(); // One-time refresh when returning to the page
    }
});

async function loadConversations() {
    if (state.isLoading) return;
    
    try {
        state.isLoading = true;
        const response = await fetch('/conversations/' + state.mode);
        const data = await response.json();
        console.log('data', data);
        const conversationsList = document.getElementById('conversations-list');
        
        // Sort conversations by last_updated timestamp (newest first)
        data.conversations.sort((a, b) => b.last_updated - a.last_updated);
        
        // Only update DOM if there are changes
        const currentConvs = conversationsList.innerHTML;
        const newConvs = data.conversations.map(conv => {
            const lastUpdated = formatTimestamp(conv.last_updated);
            let summary = '';
            if (state.mode === 'scene_chat') {
                sceneObj = JSON.parse(conv.scene);
                summary = sceneObj["场景分析"]["核心场景"];
            } else if (state.mode === 'task_chat') {
                console.log('task', conv.task);
                taskObj = JSON.parse(conv.task);
                if (taskObj.user_input) {
                    summary = taskObj.user_input;
                } else {
                    summary = 'No summary';
                }
            }
            return `
                <div class="group w-full px-3 py-2 text-sm rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors duration-200 cursor-pointer mb-2 relative" 
                     onclick="loadConversation('${conv.conversation_id}')"
                     data-conversation-id="${conv.conversation_id}">
                    <div class="flex flex-col">
                        <div class="flex items-center justify-between mb-1">
                            <div class="text-xs text-gray-600 dark:text-gray-300 italic overflow-hidden text-ellipsis flex-1">
                                ${summary || 'No summary'}
                            </div>
                            <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                <button onclick="editConversationSummary('${conv.conversation_id}', event)"
                                        class="p-1 text-gray-500 hover:text-blue-500 hover:bg-gray-300 dark:hover:bg-gray-600 rounded">
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                    </svg>
                                </button>
                                <button onclick="deleteConversation('${conv.conversation_id}', event)"
                                        class="p-1 text-gray-500 hover:text-red-500 hover:bg-gray-300 dark:hover:bg-gray-600 rounded">
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <div class="text-[10px] text-gray-500 dark:text-gray-400">
                            ${lastUpdated}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        if (currentConvs !== newConvs) {
            conversationsList.innerHTML = newConvs;
        }
    } catch (error) {
        console.error('Error loading conversations:', error);
    } finally {
        state.isLoading = false;
    }
}

async function editConversationSummary(conversationId, event) {
    event.stopPropagation(); // Prevent loading the conversation
    
    const conversationDiv = document.querySelector(`[data-conversation-id="${conversationId}"]`);
    const currentSummary = conversationDiv?.querySelector('.text-gray-600')?.textContent?.trim() || '';
    
    openSummaryModal(conversationId, currentSummary);
}



async function loadConversation(conversationId) {
    try {
        state.currentConversationId = conversationId;
        const response = await fetch(`/conversations/${state.mode}/${conversationId}`);
        const data = await response.json();
        // Clear current chat
        elements.chatMessages.innerHTML = '';
        
        // Set current conversation ID
        state.currentConversationId = conversationId;
        
        // Display messages
        for (const msg of data.messages) {
            if (msg.role === 'user') {
                console.log('msg.attachments', msg.attachments);
                appendUserMessage(msg.content, msg.message_id, msg.attachments || []);
            } else if (msg.role === 'assistant') {
                state.currentAssistantMessage = createAssistantMessage(msg.message_id);
                updateAssistantMessage(msg.content, state.currentAssistantMessage, msg.attachments || []);
                state.currentAssistantMessage = null;
            }
        }

        
        // Reset scroll state
        state.isScrolledManually = false;
        
        // Use setTimeout to ensure all content is rendered before scrolling
        setTimeout(() => {
            scrollToBottom();
        }, 100);
    } catch (error) {
        console.error('Error loading conversation:', error);
    }
}


// Add function to start new conversation
async function startNewConversation() {
    elements.chatMessages.innerHTML = '';
    if (state.mode === 'task_chat' || state.mode === 'scene_chat') {
        createFirstAssistantMessage();
    }
    
    state.currentConversationId = null;
    elements.messageInput.value = '';
    elements.fileInput.value = '';
    elements.filePreviewContainer.innerHTML = '';
    elements.filePreviewContainer.classList.add('hidden');
}

// Load conversations when page loads
document.addEventListener('DOMContentLoaded', () => {
    loadConversations();
    startNewConversation(); // Ensure we start with a new conversation
});

function appendUserMessage(content, messageId, attachments = []) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-bubble user-message relative group';
    messageDiv.dataset.messageId = messageId; // Store message ID in the DOM
    messageDiv.textContent = content;
    
    // 渲染附件
    if (attachments && attachments.length > 0) {
        attachments.forEach(file => {
            if (file.type && file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = file.data;
                img.alt = file.name;
                img.className = 'file-preview';
                img.style.cursor = 'pointer';
                img.addEventListener('click', () => showImagePreview(file.data, file.name));
                messageDiv.appendChild(img);
            } else if (file.type === 'application/pdf' || 
                      file.type === 'application/msword' || 
                      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
                // 创建文件预览容器
                const filePreview = document.createElement('div');
                filePreview.className = 'file-preview-container';
                
                // 创建文件图标
                const fileIcon = document.createElement('div');
                fileIcon.className = 'file-icon';
                fileIcon.innerHTML = file.type === 'application/pdf' ? '📄' : '📝';
                
                // 创建文件名
                const fileName = document.createElement('div');
                fileName.className = 'file-name';
                fileName.textContent = file.name;
                
                // 创建文件类型标签
                const fileType = document.createElement('div');
                fileType.className = 'file-type';
                fileType.textContent = file.type === 'application/pdf' ? 'PDF' : 'Word';
                
                // 创建下载链接
                const downloadLink = document.createElement('a');
                downloadLink.href = file.data;
                downloadLink.download = file.name;
                downloadLink.className = 'file-download';
                downloadLink.textContent = '下载';
                
                // 组装预览容器
                filePreview.appendChild(fileIcon);
                filePreview.appendChild(fileName);
                filePreview.appendChild(fileType);
                filePreview.appendChild(downloadLink);
                
                messageDiv.appendChild(filePreview);
            } else {
                // 其他类型文件
                const link = document.createElement('a');
                link.href = file.data;
                link.download = file.name;
                link.textContent = file.name;
                link.className = 'file-link';
                messageDiv.appendChild(link);
            }
        });
    }
    
    // Add edit button
    const editButton = document.createElement('button');
    // editButton.className = 'absolute top-0 right-2 p-1 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200';
    editButton.className = 'edit-button';
    editButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
    `;
    editButton.onclick = () => openEditModal(messageDiv, messageId, content);
    messageDiv.appendChild(editButton);
    
    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function createFirstAssistantMessage(content = '') {
    if (state.mode === 'scene_chat') {
        content = '你好，我是英语情景对话助手。请描述你想要练习的英语对话情景。';
    } else if (state.mode === 'task_chat') {
        content = '你好，我是任务驱动的英语学习助手。请描述你学习英语的目标。';
    } else {
        content = '你好，我是你的AI助手，有什么可以帮你的吗？';
    }
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-bubble assistant-message relative group';
    // 渲染内容
    messageDiv.innerHTML = content;
    elements.chatMessages.appendChild(messageDiv);
    
    if (!state.isScrolledManually) {
        scrollToBottom();
    }
    return messageDiv;
}
// Update the createAssistantMessage function to include content parameter
function createAssistantMessage(messageId, content = '') {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-bubble assistant-message relative group';
    messageDiv.dataset.messageId = messageId; // Store message ID in the DOM
    
    // 添加再生成按钮
    const regenerateButton = document.createElement('button');
    regenerateButton.className = 'regenerate-button';
    regenerateButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    `;
    regenerateButton.title = "Regenerate response";
    regenerateButton.onclick = () => regenerateResponse(messageDiv, messageId);
    messageDiv.appendChild(regenerateButton);

    // 添加编辑按钮
    const editButton = document.createElement('button');
    // editButton.className = 'absolute top-0 right-2 p-1 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200';
    editButton.className = 'edit-button';
    editButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
    `;
    editButton.onclick = () => openEditModal(messageDiv, messageId, content);
    messageDiv.appendChild(editButton);
    
    // 添加播放按钮
    const audioButton = document.createElement('button');
    // audioButton.className = 'absolute top-2 right-0 p-1 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200';
    audioButton.className = 'audio-button';
    audioButton.innerHTML = `
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5l-7 7 7 7V5zM19 5v14a2 2 0 01-2 2h-2a2 2 0 01-2-2V5a2 2 0 012-2h2a2 2 0 012 2z" />
    </svg>
    `;
    audioButton.onclick = () => output_audio(messageDiv, messageId, content);
    messageDiv.appendChild(audioButton);

    elements.chatMessages.appendChild(messageDiv);
    
    if (!state.isScrolledManually) {
        scrollToBottom();
    }
    return messageDiv;
}

// Add these new functions for message editing
async function openEditModal(messageDiv, messageId, content) {
    const modal = document.getElementById('message-edit-modal');
    const contentInput = document.getElementById('edit-message-content');
    const messageIdInput = document.getElementById('edit-message-id');
    const isAssistant = messageDiv.classList.contains('assistant-message');
    
    if (!messageId) {
        console.error('No message ID found');
        return;
    }
    
    // Store references for the edit operation
    state.editingMessageDiv = messageDiv;
    state.editingMessageId = messageId;
    
    try {
        // Fetch raw content from API
        const response = await fetch(`/messages/${state.mode}/${messageId}/raw`);
        if (!response.ok) throw new Error('Failed to fetch message content');
        const data = await response.json();
        
        contentInput.value = data.content;
        messageIdInput.value = messageId;
        
        // Update modal title based on message type
        const modalTitle = modal.querySelector('h3');
        modalTitle.textContent = `Edit ${isAssistant ? 'Assistant' : 'User'} Message`;
        
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        contentInput.focus();
        
    } catch (error) {
        console.error('Error fetching message content:', error);
        showNotification('Failed to load message content', 'error');
    }
}

function closeEditModal() {
    const modal = document.getElementById('message-edit-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    state.editingMessageDiv = null;
    state.editingMessageId = null;
}

// Add form submit handler for the edit modal
document.getElementById('message-edit-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const content = document.getElementById('edit-message-content').value.trim();
    const messageId = document.getElementById('edit-message-id').value;
    
    if (!content || !state.editingMessageDiv || !state.editingMessageId) return;
    
    try {
        // Save to database
        const response = await fetch(`/messages/${state.mode}/${state.editingMessageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        
        if (!response.ok) {
            throw new Error('Failed to save message');
        }
        
        closeEditModal();
        showNotification('Message updated successfully', 'success');
        
    } catch (error) {
        console.error('Error updating message:', error);
        showNotification('Failed to update message', 'error');
    }
});

// Add modal close on outside click and escape key
document.getElementById('message-edit-modal').addEventListener('click', (e) => {
    if (e.target.id === 'message-edit-modal') {
        closeEditModal();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeEditModal();
    }
});

// Update the updateAssistantMessage function
function updateAssistantMessage(content, messageDiv = null, attachments = []) {
    if (!messageDiv) {
        if (!state.currentAssistantMessage) {
            state.currentAssistantMessage = createAssistantMessage(null, '');
        }
        messageDiv = state.currentAssistantMessage;
    }

    const wasAtBottom = Math.abs(
        (elements.chatMessages.scrollHeight - elements.chatMessages.clientHeight) - elements.chatMessages.scrollTop
    ) < 10;

    // Store the existing regenerate button before updating innerHTML
    const existingRegenerateButton = messageDiv.querySelector('.regenerate-button');

    // Configure marked options and parse content
    marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false,
        highlight: function(code, language) {
            if (language && hljs.getLanguage(language)) {
                try {
                    return hljs.highlight(code, { language }).value;
                } catch (err) {}
            }
            return code;
        }
    });
    if (content.length > 1 && content.startsWith('"') && content.endsWith('"')) {
        content = content.slice(1, -1);
    }
    content = content.replace(/\\n/g, '\n');
    content = content.replace(/([^\n])###/g, '$1\n###');
    content = content.replace(/([^\n])##/g, '$1\n##');
    content = content.replace(/([^\n])#/g, '$1\n#');
    let parsedContent = marked.parse(content);
    console.log('parsedContent', parsedContent);
    parsedContent = parsedContent.replace(
        /<pre><code class="(.*?)">/g, 
        '<pre><code class="hljs $1">'
    );

    messageDiv.innerHTML = parsedContent;

    // 渲染附件
    if (attachments && attachments.length > 0) {
        attachments.forEach(file => {
            if (file.type && file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = file.data;
                img.alt = file.name;
                img.className = 'file-preview';
                img.style.cursor = 'pointer';
                img.addEventListener('click', () => showImagePreview(file.data, file.name));
                messageDiv.appendChild(img);
            } else if (file.type === 'application/pdf' || 
                      file.type === 'application/msword' || 
                      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
                // 创建文件预览容器
                const filePreview = document.createElement('div');
                filePreview.className = 'file-preview-container';
                
                // 创建文件图标
                const fileIcon = document.createElement('div');
                fileIcon.className = 'file-icon';
                fileIcon.innerHTML = file.type === 'application/pdf' ? '📄' : '📝';
                
                // 创建文件名
                const fileName = document.createElement('div');
                fileName.className = 'file-name';
                fileName.textContent = file.name;
                
                // 创建文件类型标签
                const fileType = document.createElement('div');
                fileType.className = 'file-type';
                fileType.textContent = file.type === 'application/pdf' ? 'PDF' : 'Word';
                
                // 创建下载链接
                const downloadLink = document.createElement('a');
                downloadLink.href = file.data;
                downloadLink.download = file.name;
                downloadLink.className = 'file-download';
                downloadLink.textContent = '下载';
                
                // 组装预览容器
                filePreview.appendChild(fileIcon);
                filePreview.appendChild(fileName);
                filePreview.appendChild(fileType);
                filePreview.appendChild(downloadLink);
                
                messageDiv.appendChild(filePreview);
            } else {
                // 其他类型文件
                const link = document.createElement('a');
                link.href = file.data;
                link.download = file.name;
                link.textContent = file.name;
                link.className = 'file-link';
                messageDiv.appendChild(link);
            }
        });
    }

    // Get the messageId from the div's dataset
    const messageId = messageDiv.dataset.messageId;

    // 重新添加再生成按钮
    const regenerateButton = existingRegenerateButton || document.createElement('button');
    regenerateButton.className = 'regenerate-button';
    regenerateButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    `;
    regenerateButton.title = "Regenerate response";
    regenerateButton.onclick = () => regenerateResponse(messageDiv, messageId);
    messageDiv.appendChild(regenerateButton);

    // 添加编辑按钮
    const editButton = document.createElement('button');
    // editButton.className = 'absolute top-0 right-2 p-1 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200';
    editButton.className = 'edit-button';
    editButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
    `;
    editButton.onclick = () => openEditModal(messageDiv, messageId, content);
    messageDiv.appendChild(editButton);

    // 添加播放按钮
    const audioButton = document.createElement('button');
    // audioButton.className = 'absolute top-2 right-0 p-1 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200';
    audioButton.className = 'audio-button';
    audioButton.innerHTML = `
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5l-7 7 7 7V5zM19 5v14a2 2 0 01-2 2h-2a2 2 0 01-2-2V5a2 2 0 012-2h2a2 2 0 012 2z" />
    </svg>
    `;
    audioButton.onclick = () => output_audio(messageDiv, messageId, content);
    messageDiv.appendChild(audioButton);

    // Re-apply syntax highlighting and copy buttons
    messageDiv.querySelectorAll('pre code').forEach(block => {
        const pre = block.parentNode;
        const oldButton = pre.querySelector('.copy-button');
        if (oldButton) {
            pre.removeChild(oldButton);
        }

        hljs.highlightElement(block);
        
        const copyButton = document.createElement('button');
        copyButton.className = 'copy-button';
        copyButton.textContent = 'Copy';
        copyButton.onclick = (e) => {
            e.preventDefault();
            copyToClipboard(block.textContent);
        };
        pre.appendChild(copyButton);
    });

    if (wasAtBottom && !state.isScrolledManually) {
        scrollToBottom();
    } else if (!wasAtBottom) {
        elements.jumpToBottomButton.classList.add('visible');
    }
}

// Add this new event listener for Enter key
elements.messageInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        elements.chatForm.requestSubmit();
    }
});

elements.chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = elements.messageInput.value.trim();
    const files = elements.fileInput.files;
    
    if (!message && !files.length) return;

    // Create new AbortController for this request
    state.abortController = new AbortController();

    // 立即显示用户消息和图片
    const messageId = crypto.randomUUID(); // 生成临时消息ID
    appendUserMessage(message, messageId, Array.from(files).map(file => ({
        name: file.name,
        type: file.type,
        data: URL.createObjectURL(file)
    })));

    elements.messageInput.value = '';
    elements.sendButton.disabled = true;
    elements.sendButton.classList.add('hidden');
    elements.stopButton.classList.remove('hidden');
    
    try {
        if (!state.currentConversationId) {
            const createResponse = await fetch('/create_conversation/' + state.mode, { method: 'POST' });
            const data = await createResponse.json();
            
            state.currentConversationId = data.conversation_id;
            loadConversations();
        }


        elements.filePreviewContainer.innerHTML = '';
        elements.filePreviewContainer.classList.add('hidden');
        
        elements.fileInput.value = '';

        state.currentAssistantMessage = createAssistantMessage();
        let response;
        if (state.mode === 'scene_chat') {
            const formData = new FormData();
            formData.append('message', message);
            formData.append('conversation_id', state.currentConversationId);
            response = await fetch('/dialogue/chat', {
                method: 'POST',
                body: formData,
                signal: state.abortController.signal 
            });
        }
        else if (state.mode === 'task_chat') {
            const formData = new FormData();
            formData.append('message', message);
            formData.append('conversation_id', state.currentConversationId);
            response = await fetch('/task_chat', {
                method: 'POST',
                body: formData,
                signal: state.abortController.signal 
            });
        }
        const responseText = await response.text();
        console.log('responseText', responseText);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }


        try {
            updateAssistantMessage(responseText);

            // 检查 responseText 是否包含中文字符
            const hasChinese = /[\u4e00-\u9fa5]/.test(responseText);
            if (!hasChinese) {
                // 自动点击语音播放按钮
                setTimeout(() => {
                    const lastAssistantMsg = elements.chatMessages.querySelector('.assistant-message:last-child');
                    if (lastAssistantMsg) {
                        const audioBtn = lastAssistantMsg.querySelector('.audio-button');
                        if (audioBtn) {
                            audioBtn.click();
                        }
                    }
                }, 1); 
            }

            if (!state.isScrolledManually) {
                scrollToBottom();
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Request aborted by user');
                if (responseText) {
                    db.add_message(conversation_id=state.currentConversationId, role="assistant", content=responseText);
                }
            } else {
                throw error;
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Request aborted');
        } else {
            console.error('Error:', error);
            state.currentAssistantMessage = null;
            appendMessage('Sorry, something went wrong. ' + error.message, 'assistant');
        }
    } finally {
        elements.sendButton.disabled = false;
        elements.sendButton.classList.remove('hidden');
        elements.stopButton.classList.add('hidden');
        state.abortController = null;
        
        // After streaming is complete, check if we should show jump-to-bottom button
        const isAtBottom = Math.abs(
            (elements.chatMessages.scrollHeight - elements.chatMessages.clientHeight) - elements.chatMessages.scrollTop
        ) < 10;
        if (!isAtBottom) {
            elements.jumpToBottomButton.classList.add('visible');
        }
    }
});

// Add stop button click handler
elements.stopButton.addEventListener('click', () => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send('stop_generation');
    }
});

// Add file type check function
function isValidFileType(file) {
    const validTypes = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];
    return validTypes.includes(file.type);
}

// Modify file input handling
elements.fileInput.addEventListener('change', async (e) => {
    const files = Array.from(e.target.files);
    const previewContainer = elements.filePreviewContainer;
    previewContainer.innerHTML = '';
    uploadedFiles = [];

    for (const file of files) {
        if (!isValidFileType(file)) {
            showNotification('不支持的文件类型', 'error');
            continue;
        }

        const reader = new FileReader();
        
        reader.onload = async (e) => {
            const fileData = e.target.result;
            uploadedFiles.push({
                name: file.name,
                type: file.type,
                data: fileData
            });

            const previewDiv = document.createElement('div');
            previewDiv.className = 'flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-700 rounded';

            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = fileData;
                img.className = 'w-12 h-12 object-cover rounded';
                previewDiv.appendChild(img);
            } else {
                const icon = document.createElement('div');
                icon.className = 'w-12 h-12 flex items-center justify-center bg-gray-200 dark:bg-gray-600 rounded';
                icon.innerHTML = file.type === 'application/pdf' ? '📄' : '📝';
                previewDiv.appendChild(icon);
            }

            const nameSpan = document.createElement('span');
            nameSpan.className = 'flex-1 truncate text-sm';
            nameSpan.textContent = file.name;
            previewDiv.appendChild(nameSpan);

            const removeButton = document.createElement('button');
            removeButton.className = 'p-1 text-gray-500 hover:text-red-500';
            removeButton.innerHTML = '×';
            removeButton.onclick = () => {
                previewDiv.remove();
                uploadedFiles = uploadedFiles.filter(f => f.name !== file.name);
                if (uploadedFiles.length === 0) {
                    previewContainer.classList.add('hidden');
                }
            };
            previewDiv.appendChild(removeButton);

            previewContainer.appendChild(previewDiv);
        };

        if (file.type.startsWith('image/')) {
            reader.readAsDataURL(file);
        } else {
            reader.readAsArrayBuffer(file);
        }
    }

    if (files.length > 0) {
        previewContainer.classList.remove('hidden');
    }
});

// Delete conversation handler
function deleteConversation(conversationId, event) {
    event.stopPropagation();
  
    openConfirmationModal({
      action: "delete",
      itemId: conversationId,
      title: "Delete Conversation?",
      message:
        "Are you sure you want to <strong>permanently delete</strong> this conversation? <br><br> This action <strong>cannot be undone.</strong>",
      confirmCallback: async (conversationId) => {
        try {
          const response = await fetch(`/conversations/${state.mode}/${conversationId}`, {
            method: "DELETE",
          });
  
          if (response.ok) {
            // If we're currently viewing this conversation, start a new one
            if (state.currentConversationId === conversationId) {
                startNewConversation();
            }
            loadConversations();
          } else {
            showNotification('Failed to delete conversation. Try again!', 'error');
          }
        } catch (error) {
          console.error("Error deleting conversation:", error);
        }
      },
      confirmText: "Delete",
      cancelText: "Cancel",
      color: "danger",
    });
  }
  
  // Dynamic confirmation modal
  function openConfirmationModal(modalProperties) {
    const {
      action = "",
      itemId = null,
      title = "Confirmation",
      message = "Confirmation Message",
      confirmCallback = () => {},
      confirmText = "Confirm",
      cancelText = "Cancel",
      color = "primary",
    } = modalProperties;
  
    // Set modal title and message (supports HTML)
    document.getElementById("confirmation-title").textContent = title;
    document.getElementById("confirmation-message").innerHTML = message;
  
    document.getElementById("confirmation-action").value = action;
    document.getElementById("confirmation-id").value = itemId;
  
    document.getElementById("confirm-action").textContent = confirmText;
    document.getElementById("cancel-action").textContent = cancelText;
  
    const confirmButton = document.getElementById("confirm-action");
    confirmButton.className = "px-4 py-2 text-sm text-white rounded-lg";
  
    const themeClasses =
      color === "danger"
        ? "bg-red-500 hover:bg-red-600"
        : "bg-blue-500 hover:bg-blue-600";
  
    confirmButton.classList.add(...themeClasses.split(" "));
  
    confirmButton.onclick = async () => {
      await confirmCallback(itemId);
      closeConfirmationModal();
    };
  
    document.getElementById("confirmation-modal").classList.remove("hidden");
  }
  
  function closeConfirmationModal() {
    document.getElementById("confirmation-modal").classList.add("hidden");
  }



// Add this function to handle scrolling
function handleScroll() {
    const currentScrollTop = elements.chatMessages.scrollTop;
    const maxScroll = elements.chatMessages.scrollHeight - elements.chatMessages.clientHeight;
    const isAtBottom = Math.abs(maxScroll - currentScrollTop) < 10;
    
    // Only set isScrolledManually if user is scrolling up
    if (currentScrollTop < state.lastScrollTop && !isAtBottom) {
        state.isScrolledManually = true;
    }
    
    // Show/hide jump to bottom button
    if (!isAtBottom) {
        elements.jumpToBottomButton.classList.add('visible');
    } else {
        elements.jumpToBottomButton.classList.remove('visible');
        state.isScrolledManually = false;
    }
    
    state.lastScrollTop = currentScrollTop;
}

// Add scroll event listener
elements.chatMessages.addEventListener('scroll', handleScroll);

// Update scrollToBottom function
function scrollToBottom() {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    state.isScrolledManually = false;
    elements.jumpToBottomButton.classList.remove('visible');
}

// Update your message handling functions to respect manual scrolling
function appendMessage(role, content) {
    // ...existing message appending code...
    
    // Only auto-scroll if user hasn't scrolled manually
    if (!state.isScrolledManually) {
        scrollToBottom();
    }
}

// Update your streaming response handler
async function handleStream(response) {    
    try {
        const reader = response.body.getReader();
        let partialMessage = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
                        
            // Only auto-scroll if user hasn't scrolled manually
            if (!state.isScrolledManually) {
                scrollToBottom();
            }
        }
    } catch (error) {
        console.error('Error reading stream:', error);
    }
}

// Initialize settings panel
async function initializeSettings() {
    if (state.isInitializingSettings) return;
    try {
        state.isInitializingSettings = true;
        
        // Get all available settings
        const response = await fetch('/settings/all');
        if (!response.ok) throw new Error('Failed to fetch settings');
        
        const data = await response.json();
        const selector = document.getElementById('settings-selector');
        
        // Clear existing options
        while (selector.firstChild) {
            selector.removeChild(selector.firstChild);
        }
        
        // Get default settings to mark as selected
        const defaultResponse = await fetch('/settings');
        if (!defaultResponse.ok) throw new Error('Failed to fetch default settings');
        const defaultSettings = await defaultResponse.json();
        
        // Create a Map to track unique settings by ID
        const uniqueSettings = new Map();
        
        // Add unique settings to the Map
        if (data.settings && Array.isArray(data.settings)) {
            data.settings.forEach(setting => {
                // Only add if we haven't seen this ID before and the setting has a valid ID
                if (setting && setting.id && !uniqueSettings.has(setting.id)) {
                    uniqueSettings.set(setting.id, setting);
                }
            });
        }
        
        // Remove any existing change listener to prevent duplicates
        const oldSelector = selector.cloneNode(false);
        selector.parentNode.replaceChild(oldSelector, selector);
        
        // Convert Map values to array and sort by name
        const sortedSettings = Array.from(uniqueSettings.values())
            .sort((a, b) => a.name.localeCompare(b.name));
        
        // Populate selector with unique settings
        sortedSettings.forEach(setting => {
            const option = document.createElement('option');
            option.value = setting.id;
            option.textContent = setting.name;
            option.selected = setting.id === defaultSettings.id;
            oldSelector.appendChild(option);
        });
        
        // Add new change listener
        oldSelector.addEventListener('change', (e) => loadSettingsConfig(e.target.value));
        
        // Load selected settings if any options were added
        if (oldSelector.options.length > 0) {
            await loadSettingsConfig(oldSelector.value);
        }
        
        // Add input listeners for change detection
        addSettingsChangeListeners();
        
    } catch (error) {
        console.error('Failed to initialize settings:', error);
        alert('Error loading settings configurations');
    } finally {
        state.isInitializingSettings = false;
    }
}

async function handleComponentRequest(componentType) {
    if (componentType !== 'smart-reply') {
        openTranslateModal();
    }
    
    console.log(`Handling ${componentType} request...`);
    const message = elements.messageInput.value;
    
    // if (!message) return;
    const formData = new FormData();
    formData.append('text', message);
    formData.append('conversation_id', state.currentConversationId);
    
    try {
        const response = await fetch(`/components/${state.mode}/${componentType}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.text();
        // 去除首尾字符
        console.log(`Received ${componentType} result:`, result);
        if (result && result.length > 2) {
            if (componentType !== 'smart-reply') {
                document.querySelector('.translated-text').textContent = result.slice(1, -1);
            }
            else{
                elements.messageInput.value = result.slice(1, -1);
            }
        }

        
    } catch (error) {
        console.error(`${componentType}处理失败:`, error);
    }
}

// Update loadSettingsConfig to automatically set selected as default
async function loadSettingsConfig(id) {
    try {
        const response = await fetch(`/settings/${id}`);
        if (!response.ok) throw new Error('Failed to fetch settings config');
        
        const settings = await response.json();
        updateSettingsForm(settings);
        
        // Store current and original settings
        state.currentSettings = settings;
        state.originalSettings = {...settings};
        
        // Set this configuration as default automatically
        await fetch(`/settings/${id}/set_default`, { method: 'POST' });
        
        // Hide warning
        document.getElementById('settings-warning').classList.add('hidden');
        
    } catch (error) {
        console.error('Failed to load settings config:', error);
        alert('Error loading settings configuration');
    }
}

// Update form with settings values
function updateSettingsForm(settings) {
    document.getElementById('config-name').value = settings.name || '';
    document.getElementById('temperature').value = settings.temperature || 1.0;
    document.getElementById('temperature-value').textContent = settings.temperature || 1.0;
    document.getElementById('top-p').value = settings.top_p || 0.95;
    document.getElementById('top-p-value').textContent = settings.top_p || 0.95;
    document.getElementById('max-tokens').value = settings.max_tokens || 4096;
    document.getElementById('api-host').value = settings.host || '';
    document.getElementById('model-name').value = settings.model_name || '';
    document.getElementById('api-key').value = settings.api_key || '';
    document.getElementById('tavily-api-key').value = settings.tavily_api_key || '';
    // Store timestamps if they exist
    state.currentSettings = {
        ...settings,
        updated_at: settings.updated_at,
        created_at: settings.created_at
    };
}

// Create new settings configuration
async function createNewSettingsConfig() {
    openSettingsModal();
}

// Update saveSettings function to remove default toggle handling
async function saveSettings() {
    const saveButton = document.getElementById('settings-warning')?.querySelector('button');
    if (saveButton) {
        saveButton.disabled = true;
    }
    
    try {
        const settings = {
            name: document.getElementById('config-name').value.trim(),
            temperature: parseFloat(document.getElementById('temperature').value),
            top_p: parseFloat(document.getElementById('top-p').value),
            max_tokens: parseInt(document.getElementById('max-tokens').value),
            host: document.getElementById('api-host').value.trim(),
            model_name: document.getElementById('model-name').value.trim(),
            api_key: document.getElementById('api-key').value.trim(),
            tavily_api_key: document.getElementById('tavily-api-key').value.trim(),
            updated_at: state.currentSettings?.updated_at,
            created_at: state.currentSettings?.created_at
        };
        
        if (!settings.name) {
            alert('Configuration name is required');
            return;
        }

        let response;
        let result;
        
        // If this is a new configuration
        if (state.currentSettings.id === 'new') {
            response = await fetch('/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
        } else {
            // Update existing configuration
            settings.id = state.currentSettings.id;
            response = await fetch(`/settings/${settings.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
        }
        
        if (!response.ok) {
            throw new Error('Failed to save settings');
        }
        
        result = await response.json();
        
        // For new settings, we need the ID from the response
        const settingsId = state.currentSettings.id === 'new' ? result.id : settings.id;
        
        // Set as default automatically
        const defaultResponse = await fetch(`/settings/${settingsId}/set_default`, {
            method: 'POST'
        });
        
        if (!defaultResponse.ok) {
            throw new Error('Failed to set as default');
        }

        // Update the current settings state
        state.currentSettings = {
            ...settings,
            id: settingsId
        };
        state.originalSettings = {...state.currentSettings};
        
        // Hide the warning since we just saved
        document.getElementById('settings-warning').classList.add('hidden');
        
        // Refresh the settings list and reselect current settings
        await initializeSettings();
        document.getElementById('settings-selector').value = settingsId;
        
        // Show success feedback
        const successNotification = document.createElement('div');
        successNotification.className = 'fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-50 flex items-center gap-2 animate-fade-in';
        successNotification.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <span>Settings saved successfully</span>
        `;
        
        document.body.appendChild(successNotification);
        
        // Add fade out animation
        setTimeout(() => {
            successNotification.classList.add('opacity-0', 'transform', 'translate-y-[-1rem]');
            successNotification.style.transition = 'all 0.5s ease-out';
        }, 1500);
        
        // Remove the notification after animation
        setTimeout(() => {
            successNotification.remove();
        }, 2000);
        
    } catch (error) {
        console.error('Failed to save settings:', error);
        
        // Show error notification
        const errorNotification = document.createElement('div');
        errorNotification.className = 'fixed top-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg z-50 flex items-center gap-2 animate-fade-in';
        errorNotification.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
            <span>Error saving settings: ${error.message}</span>
        `;
        
        document.body.appendChild(errorNotification);
        
        setTimeout(() => {
            errorNotification.classList.add('opacity-0', 'transform', 'translate-y-[-1rem]');
            errorNotification.style.transition = 'all 0.5s ease-out';
        }, 3000);
        
        setTimeout(() => {
            errorNotification.remove();
        }, 3500);
    } finally {
        if (saveButton) {
            saveButton.disabled = false;
        }
    }
}

// Update addSettingsChangeListeners to remove default-config-toggle
function addSettingsChangeListeners() {
    const inputs = [
        'config-name', 'temperature', 'top-p', 'max-tokens',
        'api-host', 'model-name', 'api-key', 'tavily-api-key'
    ];
    
    inputs.forEach(id => {
        document.getElementById(id).addEventListener('input', checkSettingsChanged);
    });
}

// Check if settings have changed
function checkSettingsChanged() {
    if (!state.originalSettings) return;
    
    const current = {
        id: document.getElementById('settings-selector').value,
        name: document.getElementById('config-name').value.trim(),
        temperature: parseFloat(document.getElementById('temperature').value),
        top_p: parseFloat(document.getElementById('top-p').value),
        max_tokens: parseInt(document.getElementById('max-tokens').value),
        host: document.getElementById('api-host').value.trim(),
        model_name: document.getElementById('model-name').value.trim(),
        api_key: document.getElementById('api-key').value.trim(),
        tavily_api_key: document.getElementById('tavily-api-key').value.trim(),
        updated_at: state.currentSettings?.updated_at,
        created_at: state.currentSettings?.created_at
    };
    
    const hasChanged = JSON.stringify(current) !== JSON.stringify(state.originalSettings);
    document.getElementById('settings-warning').classList.toggle('hidden', !hasChanged);
}

// Initialize settings when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Initialize core functionality
    loadConversations();
    startNewConversation();
    connectWebSocket();
    
    // Initialize settings only once
    initializeSettings();
    
    // Add event listeners
    document.getElementById('new-conversation-btn')?.addEventListener('click', startNewConversation);
    elements.chatMessages.addEventListener('scroll', handleScroll);
    handleScroll();
}, { once: true }); // Add {once: true} to ensure it only runs once



// Add this new helper function for notifications
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 flex items-center gap-2 animate-fade-in ${
        type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
    }`;
    
    const icon = document.createElement('svg');
    icon.className = 'w-4 h-4';
    icon.setAttribute('fill', 'none');
    icon.setAttribute('stroke', 'currentColor');
    icon.setAttribute('viewBox', '0 0 24 24');
    
    if (type === 'success') {
        icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>';
    } else {
        icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>';
    }
    
    notification.appendChild(icon);
    notification.appendChild(document.createTextNode(message));
    
    document.body.appendChild(notification);
    
    // Add fade out animation
    setTimeout(() => {
        notification.classList.add('opacity-0', 'transform', 'translate-y-[-1rem]');
        notification.style.transition = 'all 0.5s ease-out';
    }, type === 'success' ? 1500 : 3000);
    
    // Remove the notification after animation
    setTimeout(() => {
        notification.remove();
    }, type === 'success' ? 2000 : 3500);
}



function openSettingsModal() {
    const modal = document.getElementById('settings-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    
    // Clear and focus the input
    const nameInput = document.getElementById('new-config-name');
    nameInput.value = '';
    nameInput.focus();
}

function closeSettingsModal() {
    const modal = document.getElementById('settings-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

// Replace the old createNewSettingsConfig function with this one
async function createNewSettingsConfig() {
    openSettingsModal();
}

// Add new form submit handler for the settings modal
document.getElementById('new-settings-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('new-config-name').value.trim();
    const template = document.getElementById('settings-template').value;
    
    if (!name) {
        alert('Configuration name is required');
        return;
    }
    
    try {
        let defaultSettings;
        
        if (template === 'copy-current') {
            // Use current settings as template
            defaultSettings = {
                ...state.currentSettings,
                name: name,
                id: 'new'
            };
        } else {
            // Fetch default template
            const response = await fetch('/default_settings');
            if (!response.ok) throw new Error('Failed to fetch default values');
            defaultSettings = await response.json();
            defaultSettings.name = name;
            defaultSettings.id = 'new';
        }
        
        // Update form with new settings
        updateSettingsForm(defaultSettings);
        
        // Update stored settings state
        state.currentSettings = defaultSettings;
        state.originalSettings = null;
        
        // Show the unsaved changes warning
        document.getElementById('settings-warning').classList.remove('hidden');
        
        closeSettingsModal();
        
    } catch (error) {
        console.error('Failed to create new settings:', error);
        alert('Error creating new configuration');
    }
});

// Add click handler to close modal when clicking outside
document.getElementById('settings-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'settings-modal') {
        closeSettingsModal();
    }
});

// Update DOM Content Loaded event listener to include modal handlers
document.addEventListener('DOMContentLoaded', () => {
    // ...existing initialization code...
    
    // Add settings modal close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeSettingsModal();
        }
    });
    
}, { once: true });


async function regenerateResponse(messageDiv, messageId) {
    // Get conversation context
    const conversationId = state.currentConversationId;
    if (!conversationId || !messageId) return;

    // Disable regenerate button and show loading state
    const regenerateButton = messageDiv.querySelector('.regenerate-button');
    const originalButtonHtml = regenerateButton.innerHTML;
    regenerateButton.innerHTML = `
        <svg class="w-4 h-4 regenerate-spinner" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    `;
    regenerateButton.disabled = true;

    try {
        // Create FormData for the request
        const formData = new FormData();
        formData.append('message', ''); // Empty message since we're regenerating
        formData.append('conversation_id', conversationId);
        formData.append('message_id', messageId);
        formData.append('client_id', state.clientId)
        // Make request to regenerate endpoint
        const response = await fetch('/regenerate_response', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let responseText = '';

        while (true) {
            const {value, done} = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            responseText += chunk;
            
            // Update the message content
            updateAssistantMessage(responseText, messageDiv);
        }

    } catch (error) {
        console.error('Error regenerating response:', error);
        showNotification('Failed to regenerate response', 'error');
    } finally {
        // Restore regenerate button
        regenerateButton.innerHTML = originalButtonHtml;
        regenerateButton.disabled = false;
    }
}

function handleVisibilityChange() {
    if (document.hidden) {
        // Optional: Close WebSocket when page is hidden
        // if (state.ws) state.ws.close();
    } else {
        // Ensure we have a connection when page becomes visible
        if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
            connectWebSocket();
        }
        // Refresh conversations list when returning to the page
        loadConversations();
    }
}

function openSummaryModal(conversationId, currentSummary) {
    const modal = document.getElementById('summary-edit-modal');
    const contentInput = document.getElementById('edit-summary-content');
    const conversationIdInput = document.getElementById('edit-summary-conversation-id');
    
    contentInput.value = currentSummary === 'No summary' ? '' : currentSummary;
    conversationIdInput.value = conversationId;
    
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    contentInput.focus();
}

function closeSummaryModal() {
    const modal = document.getElementById('summary-edit-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

// Add form submit handler for the summary edit modal
document.getElementById('summary-edit-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const content = document.getElementById('edit-summary-content').value.trim();
    const conversationId = document.getElementById('edit-summary-conversation-id').value;
    
    try {
        const formData = new FormData();
        formData.append('summary', content);
        
        const response = await fetch(`/conversations/${state.mode}/${conversationId}/summary`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Failed to update summary');
        
        // Update the UI
        const conversationDiv = document.querySelector(`[data-conversation-id="${conversationId}"]`);
        const summaryElement = conversationDiv.querySelector('.text-gray-600');
        if (summaryElement) {
            summaryElement.textContent = content || 'No summary';
        }
        
        closeSummaryModal();
        showNotification('Summary updated successfully', 'success');
        
    } catch (error) {
        console.error('Error updating summary:', error);
        showNotification('Failed to update summary', 'error');
    }
});

// Add modal close handlers
document.getElementById('summary-edit-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'summary-edit-modal') {
        closeSummaryModal();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeSummaryModal();
    }
});

// 打开翻译弹窗
function openTranslateModal() {
    const modal = document.getElementById('translate-modal');
    const modalContent = modal.querySelector('div');

    const inputArea = document.getElementById('message-input');

    const inputRect = inputArea.getBoundingClientRect();

    // 计算弹框位置
    const modalHeight = modalContent.offsetHeight;
    const topPosition = inputRect.top - modalHeight - 165;
    
    // 设置弹框位置
    modalContent.style.top = `${topPosition}px`;
    modalContent.style.left = `${inputRect.left}px`;
    
    // 显示弹框并设置文本
    modal.classList.remove('hidden');

    const originalText = inputArea.value.trim();
    if (originalText) {
        document.querySelector('.original-text').textContent = originalText;
    }
}

// 关闭翻译弹窗
function closeTranslateModal() {
    const modal = document.getElementById('translate-modal');
    modal.classList.add('hidden');
    // 清除位置样式和内容
    const modalContent = modal.querySelector('div');
    modalContent.style.top = '';
    modalContent.style.left = '';
    document.querySelector('.original-text').textContent = '';
    document.querySelector('.translated-text').textContent = '';
}

// 接受翻译
function acceptTranslation() {
    const translatedText = document.querySelector('.translated-text').textContent;
    if (translatedText) {
        document.getElementById('message-input').value = translatedText;
    }
    closeTranslateModal();
}

// 添加点击外部关闭弹框的功能
document.addEventListener('click', (event) => {
    const modal = document.getElementById('translate-modal');
    // 检查是否点击了模态框外部，且不是任何组件请求按钮
    if (!modal.contains(event.target) && 
        !event.target.closest('button[onclick^="handleComponentRequest"]')) {
        closeTranslateModal();
    }
});

// // 监听输入框变化，实时更新翻译
// document.getElementById('message-input').addEventListener('input', (event) => {
//     const modal = document.getElementById('translate-modal');
//     if (!modal.classList.contains('hidden')) {
//         const text = event.target.value.trim();
//         document.querySelector('.original-text').textContent = text;
//         if (text) {
//             handleTranslate(text);
//         } else {
//             document.querySelector('.translated-text').textContent = '';
//         }
//     }
// });

// 错题本类型与错误类型的映射
const errorTypeOptions = {
    writing_error_book: [
        { value: '', label: '全部' },
        { value: '语法错误', label: '语法错误' },
        { value: '主题偏离', label: '主题偏离' },
        { value: '回答不完整', label: '回答不完整' },
        { value: '用词不当', label: '用词不当' }
    ],
    listening_error_book: [
        { value: '', label: '全部' },
        { value: '理解偏差', label: '理解偏差' },
        { value: '听写错误', label: '听写错误' },
        { value: '遗漏要点', label: '遗漏要点' }
    ],
    scene_error_book: [
        { value: '', label: '全部' },
        { value: '语法错误', label: '语法错误' },
        { value: '主题偏离', label: '主题偏离' },
        { value: '回答不完整', label: '回答不完整' },
        { value: '用词不当', label: '用词不当' }
    ],
    reading_error_book: [
        { value: '', label: '全部' },
        { value: '理解偏差', label: '理解偏差' },
        { value: '遗漏要点', label: '遗漏要点' },
        { value: '表达不清', label: '表达不清' }
    ]
};

function updateErrorTypeSelect() {
    const bookType = document.getElementById('error-book-select').value;
    const errorTypeSelect = document.getElementById('error-type-select');
    if (errorTypeSelect) {
        errorTypeSelect.innerHTML = '';
        (errorTypeOptions[bookType] || [{ value: '', label: '全部' }]).forEach(opt => {
            const option = document.createElement('option');
            option.value = opt.value;
            option.textContent = opt.label;
            errorTypeSelect.appendChild(option);
        });
    }
}

// 监听错题本类型切换
const errorBookSelect = document.getElementById('error-book-select');
if (errorBookSelect) {
    errorBookSelect.addEventListener('change', updateErrorTypeSelect);
}

// 监听"确定"按钮
const filterConfirmBtn = document.getElementById('filter-confirm-btn');
if (filterConfirmBtn) {
    filterConfirmBtn.addEventListener('click', function() {
        const bookType = document.getElementById('error-book-select').value;
        const errorType = document.getElementById('error-type-select').value;
        const isCorrected = document.getElementById('is-corrected-select').value;
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;

        // 组装参数
        const params = {
            book: bookType,
            error_type: errorType,
            is_corrected: isCorrected,
            start_date: startDate,
            end_date: endDate
        };

        // 发请求（你需要后端支持这些参数）
        fetch('/api/wrong_list?' + new URLSearchParams(params))
            .then(resp => resp.json())
            .then(data => {
                renderWrongList(data);
            })
            .catch(() => {
                document.getElementById('wrong-list').innerHTML = '<li>加载失败</li>';
            });
    });
}

document.addEventListener('DOMContentLoaded', updateErrorTypeSelect);

// 动态渲染错题筛选项
async function updateDynamicFilters() {
    const bookType = document.getElementById('error-book-select').value;
    const resp = await fetch(`/api/error_filter_options?book=${bookType}`);
    const data = await resp.json();
    const container = document.getElementById('dynamic-filters');
    container.innerHTML = '';
    (data.filters || []).forEach(filter => {
        const label = document.createElement('label');
        label.textContent = filter.name + '：';
        label.className = 'ml-2';
        container.appendChild(label);
        if (filter.options) {
            const select = document.createElement('select');
            select.id = filter.key + '-select';
            select.className = 'p-1 rounded border border-gray-300 dark:bg-gray-700 dark:text-gray-100 ml-1';
            filter.options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.label;
                select.appendChild(option);
            });
            container.appendChild(select);
        } else if (filter.type === 'number_range') {
            // 复习次数区间
            const minInput = document.createElement('input');
            minInput.type = 'number';
            minInput.id = filter.key + '-min';
            minInput.placeholder = '最小';
            minInput.className = 'p-1 rounded border border-gray-300 dark:bg-gray-700 dark:text-gray-100 ml-1';
            const maxInput = document.createElement('input');
            maxInput.type = 'number';
            maxInput.id = filter.key + '-max';
            maxInput.placeholder = '最大';
            maxInput.className = 'p-1 rounded border border-gray-300 dark:bg-gray-700 dark:text-gray-100 ml-1';
            container.appendChild(minInput);
            container.appendChild(document.createTextNode(' - '));
            container.appendChild(maxInput);
        } else if (filter.type === 'date_range') {
            // 日期区间
            const startInput = document.createElement('input');
            startInput.type = 'date';
            startInput.id = filter.key + '-start';
            startInput.className = 'p-1 rounded border border-gray-300 dark:bg-gray-700 dark:text-gray-100 ml-1';
            const endInput = document.createElement('input');
            endInput.type = 'date';
            endInput.id = filter.key + '-end';
            endInput.className = 'p-1 rounded border border-gray-300 dark:bg-gray-700 dark:text-gray-100 ml-1';
            container.appendChild(startInput);
            container.appendChild(document.createTextNode(' - '));
            container.appendChild(endInput);
        }
    });
}

document.getElementById('error-book-select').addEventListener('change', updateDynamicFilters);
document.addEventListener('DOMContentLoaded', updateDynamicFilters);

// 确定按钮收集所有筛选项并请求错题列表
function collectFilterParams() {
    const params = { book: document.getElementById('error-book-select').value };
    const container = document.getElementById('dynamic-filters');
    container.querySelectorAll('select').forEach(sel => {
        const key = sel.id.replace(/-select$/, '');
        params[key] = sel.value;
    });
    container.querySelectorAll('input[type="number"]').forEach(input => {
        if (input.value) params[input.id] = input.value;
    });
    container.querySelectorAll('input[type="date"]').forEach(input => {
        if (input.value) params[input.id] = input.value;
    });
    return params;
}

document.getElementById('filter-confirm-btn').addEventListener('click', function() {
    const params = collectFilterParams();
    fetch('/api/wrong_list?' + new URLSearchParams(params))
        .then(resp => resp.json())
        .then(data => {
            renderWrongList(data);
        })
        .catch(() => {
            document.getElementById('wrong-list').innerHTML = '<li>加载失败</li>';
        });
});




let errorData = [];
let currentErrorIndex = 0;

function renderErrorDetail(idx) {
  if (!errorData.length) return;
  const item = errorData[idx];
  const container = document.getElementById('error-detail-container');
  container.innerHTML = `
    <div class="p-4 bg-gray-50 dark:bg-gray-900/30 rounded flex flex-col gap-2">
      <div class="p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 text-sm">
        <strong>题目：</strong>${item.question || ''}
      </div>
      <div class="p-2 bg-red-50 dark:bg-red-900/30 rounded border border-red-200 dark:border-red-700 text-sm">
        <strong>错误类型：</strong>${item.error_type || ''}<br>
        <strong>错误描述：</strong>${item.error_description || ''}<br>
        <strong>AI评语：</strong>${item.feedback || ''}
      </div>
      <div class="p-2 bg-green-50 dark:bg-green-900/30 rounded border border-green-200 dark:border-green-700 text-sm">
        <strong>标准答案：</strong>${item.answer || ''}
      </div>
    </div>
  `;
  document.getElementById('error-index-info').textContent = `第 ${idx + 1} / ${errorData.length} 题`;
  document.getElementById('prev-error-btn').disabled = idx === 0;
  document.getElementById('next-error-btn').disabled = idx === errorData.length - 1;
}

document.getElementById('prev-error-btn').onclick = function() {
  if (currentErrorIndex > 0) {
    currentErrorIndex--;
    renderErrorDetail(currentErrorIndex);
  }
};
document.getElementById('next-error-btn').onclick = function() {
  if (currentErrorIndex < errorData.length - 1) {
    currentErrorIndex++;
    renderErrorDetail(currentErrorIndex);
  }
};

function onWrongListLoaded(data) {
  errorData = data || [];
  currentErrorIndex = 0;
  if (errorData.length > 0) {
    renderErrorDetail(0);
  } else {
    document.getElementById('error-detail-container').innerHTML = '<div class="text-gray-400">暂无错题</div>';
    document.getElementById('error-index-info').textContent = '';
    document.getElementById('prev-error-btn').disabled = true;
    document.getElementById('next-error-btn').disabled = true;
  }
}

// 你的 fetch 代码里这样用
document.getElementById('filter-confirm-btn').addEventListener('click', function() {
  // ...参数收集...
  const bookType = document.getElementById('error-book-select').value;
  fetch('/api/wrong_list?book=' + encodeURIComponent(bookType))
    .then(resp => resp.json())
    .then(data => onWrongListLoaded(data))
    .catch(() => {
      document.getElementById('error-detail-container').innerHTML = '<div class="text-gray-400">加载失败</div>';
    });
});

