if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    let mediaStream;
    let mediaRecorder;
    let isRecording = false;

    window.addEventListener('DOMContentLoaded', () => {
        const voiceButton = document.getElementById('voice-button');
        const messageInput = document.getElementById('message-input');
        if (!voiceButton || !messageInput) return;

        voiceButton.addEventListener('click', async () => {
            if (isRecording) {
                mediaRecorder.stop();
                mediaStream.getTracks().forEach(track => track.stop());
                voiceButton.innerHTML = '<i class="fas fa-microphone"></i>';
                voiceButton.classList.remove('bg-red-500', 'text-white');
                voiceButton.classList.add('bg-gray-200', 'text-gray-700', 'dark:bg-gray-600', 'dark:text-gray-200');
                messageInput.placeholder = '请输入内容...';
                isRecording = false;
                return;
            }

            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(mediaStream);
                let audioChunks = [];

                mediaRecorder.ondataavailable = (e) => {
                    audioChunks.push(e.data);
                };
                let hasAppendedSpeech = false;
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'recording.webm');

                    try {
                        const response = await fetch('/speech_to_text', {
                            method: 'POST',
                            body: formData
                        });

                        if (response.ok) {
                            const result = await response.json();
                            const text = result.text;

                            // === 核心逻辑 ===
                            if (!hasAppendedSpeech) {
                                messageInput.value += text;
                                hasAppendedSpeech = true;
                            } else {
                                messageInput.value += '。' + text;
                            }
                        } else {
                            messageInput.placeholder = '识别失败，请重试';
                        }
                    } catch (err) {
                        console.error('上传失败:', err);
                        messageInput.placeholder = '上传失败，请检查网络';
                    }
                };

                mediaRecorder.start();
                voiceButton.innerHTML = '<i class="fas fa-stop"></i>';
                voiceButton.classList.remove('bg-gray-200', 'text-gray-700', 'dark:bg-gray-600', 'dark:text-gray-200');
                voiceButton.classList.add('bg-red-500', 'text-white');
                messageInput.placeholder = '正在聆听...';
                isRecording = true;
            } catch (error) {
                console.error('麦克风访问错误:', error);
                alert('无法访问麦克风，请检查浏览器权限设置');
                messageInput.placeholder = '麦克风访问错误，请重试';
            }
        });
    });
}
