// 加载学习情况数据
async function loadStudyStatus() {
    try {
        console.log('开始加载学习统计数据');
        const response = await fetch('/api/study-status');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('获取到的学习统计数据:', data);
        
        // 更新学习时长
        const studyDurationElement = document.querySelector('.study-duration');
        if (studyDurationElement) {
            studyDurationElement.textContent = data.study_duration;
        }
        
        // 更新错题统计图表
        const errorCtx = document.getElementById('error-chart');
        if (!errorCtx) {
            console.error('找不到错题统计图表元素');
            return;
        }

        // 更新柱状图
        if (window.errorChart) {
            window.errorChart.destroy();
        }
        
        console.log('创建柱状图，数据:', {
            listening: data.error_counts.listening,
            reading: data.error_counts.reading,
            writing: data.error_counts.writing
        });
        
        const ctx = errorCtx.getContext('2d');
        console.log('Canvas context:', ctx);
        
        window.errorChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['听力', '阅读', '写作'],
                datasets: [{
                    data: [
                        data.error_counts.listening,
                        data.error_counts.reading,
                        data.error_counts.writing
                    ],
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 206, 86, 0.8)'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        display: false  // 隐藏图例
                    }
                },
                barPercentage: 0.3,
                categoryPercentage: 0.5
            }
        });
        
        console.log('柱状图创建完成');

        // 更新周错题趋势图表
        const weeklyCtx = document.getElementById('weekly-error-chart');
        if (!weeklyCtx) {
            console.error('找不到周错题趋势图表元素');
            return;
        }
        
        if (window.weeklyChart) {
            window.weeklyChart.destroy();
        }
        
        window.weeklyChart = new Chart(weeklyCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.weekly_errors.dates,
                datasets: [
                    {
                        label: '听力错题',
                        data: data.weekly_errors.listening,
                        borderColor: 'rgba(255, 99, 132, 1)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: '阅读错题',
                        data: data.weekly_errors.reading,
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: '写作错题',
                        data: data.weekly_errors.writing,
                        borderColor: 'rgba(255, 206, 86, 1)',
                        backgroundColor: 'rgba(255, 206, 86, 0.1)',
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            boxWidth: 12,
                            padding: 15
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('加载学习统计数据失败:', error);
    }
}