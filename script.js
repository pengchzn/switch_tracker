// 全局变量
let gameData = null;

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化标签页切换
    initTabSwitching();
    
    // 加载游戏数据
    loadGameData();
    
    // 绑定刷新按钮事件
    document.getElementById('refresh-data').addEventListener('click', function() {
        loadGameData(true);
    });
    
    // 绑定游戏搜索事件
    document.getElementById('game-search').addEventListener('input', function() {
        filterGames(this.value);
    });
    
    // 绑定游戏排序事件
    document.getElementById('sort-games').addEventListener('change', function() {
        sortGames(this.value);
    });
    
    // 初始化游戏日历
    initGameCalendar();
    
    // 绑定日历导航按钮事件
    document.getElementById('prev-month').addEventListener('click', function() {
        navigateCalendar(-1);
    });
    
    document.getElementById('next-month').addEventListener('click', function() {
        navigateCalendar(1);
    });
});

// 初始化标签页切换功能
function initTabSwitching() {
    const tabs = document.querySelectorAll('.sidebar nav li');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // 移除所有标签的活动状态
            tabs.forEach(t => t.classList.remove('active'));
            
            // 添加当前标签的活动状态
            this.classList.add('active');
            
            // 获取目标标签页
            const targetTab = this.getAttribute('data-tab');
            
            // 隐藏所有标签页内容
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // 显示目标标签页内容
            document.getElementById(targetTab).classList.add('active');
        });
    });
}

// 加载游戏数据
function loadGameData(forceRefresh = false) {
    const lastUpdated = localStorage.getItem('lastUpdated');
    const cachedData = localStorage.getItem('gameData');
    
    // 如果强制刷新，或者没有缓存数据，或者缓存已过期（24小时），则从服务器获取数据
    if (forceRefresh || !cachedData || !lastUpdated || (Date.now() - parseInt(lastUpdated)) > 24 * 60 * 60 * 1000) {
        document.getElementById('loading-indicator').style.display = 'flex';
        
        // 确保API请求绝对路径
        const baseUrl = window.location.origin;
        
        // 使用Promise.all同时获取游戏数据和最近活动
        Promise.all([
            fetch(`${baseUrl}/api/games`).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            }),
            fetch(`${baseUrl}/api/recent_activities`).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
        ])
        .then(([gamesData, recentData]) => {
            // 添加更多调试日志
            console.log('原始API数据:', { gamesData, recentData });
            
            // 转换游戏数据格式以兼容旧代码
            const playHistories = gamesData.map(game => ({
                titleId: game.title_id,
                titleName: game.name,
                originalName: game.original_name, 
                imageUrl: game.image_url,
                deviceType: game.device_type,
                firstPlayedAt: game.first_played_at,
                lastPlayedAt: game.last_played_at,
                totalPlayedDays: game.total_played_days,
                totalPlayedMinutes: game.total_played_minutes
            }));
            
            // 合并数据
            const combinedData = {
                playHistories: playHistories,
                recentPlayHistories: recentData.recentPlayHistories || [],
                lastUpdatedAt: new Date().toISOString()
            };
            
            console.log('处理后的数据:', combinedData);
            console.log('游戏列表:', combinedData.playHistories.length, '条记录');
            console.log('最近活动:', combinedData.recentPlayHistories.length, '条记录');
            
            // 缓存数据
            localStorage.setItem('gameData', JSON.stringify(combinedData));
            localStorage.setItem('lastUpdated', Date.now().toString());
            
            // 更新UI
            updateLastUpdated(combinedData.lastUpdatedAt);
            updateOverview(combinedData);
            updateRecentActivity(combinedData.recentPlayHistories);
            updateRecentTab(combinedData.recentPlayHistories);
            updateGamesList(combinedData.playHistories);
            
            document.getElementById('loading-indicator').style.display = 'none';
            console.log('数据加载成功', combinedData);
        })
        .catch(error => {
            console.error('获取游戏数据失败:', error);
            document.getElementById('loading-indicator').style.display = 'none';
            
            // 如果API请求失败但有本地缓存数据，回退到本地缓存
            if (cachedData) {
                console.log('使用缓存数据');
                const data = JSON.parse(cachedData);
                updateLastUpdated(data.lastUpdatedAt);
                updateOverview(data);
                updateRecentActivity(data.recentPlayHistories);
                updateRecentTab(data.recentPlayHistories);
                updateGamesList(data.playHistories);
            } else {
                // 显示一个错误消息
                alert('无法加载游戏数据，请确保您已运行数据获取脚本');
            }
        });
    } else {
        // 使用缓存数据
        const data = JSON.parse(cachedData);
        updateLastUpdated(data.lastUpdatedAt);
        updateOverview(data);
        updateRecentActivity(data.recentPlayHistories);
        updateRecentTab(data.recentPlayHistories);
        updateGamesList(data.playHistories);
    }
}

// 更新最后更新时间
function updateLastUpdated(timestamp) {
    const date = new Date(timestamp);
    const formattedDate = `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    document.getElementById('last-updated').textContent = formattedDate;
}

// 更新概览页面
function updateOverview(data) {
    // 更新总游戏数
    document.getElementById('total-games').textContent = data.playHistories.length;
    
    // 计算总游玩时间
    const totalMinutes = data.playHistories.reduce((total, game) => total + game.totalPlayedMinutes, 0);
    const totalHours = Math.floor(totalMinutes / 60);
    document.getElementById('total-playtime').textContent = `${totalHours}小时${totalMinutes % 60}分钟`;
    
    // 找出游玩时间最长的游戏
    const mostPlayedGame = data.playHistories.reduce((prev, current) => 
        (prev.totalPlayedMinutes > current.totalPlayedMinutes) ? prev : current
    );
    
    document.getElementById('most-played-game').textContent = mostPlayedGame.titleName;
    const mostPlayedHours = Math.floor(mostPlayedGame.totalPlayedMinutes / 60);
    document.getElementById('most-played-time').textContent = 
        `${mostPlayedHours}小时${mostPlayedGame.totalPlayedMinutes % 60}分钟`;
    
    // 创建游玩时间分布图表
    createPlaytimeChart(data.playHistories);
    
    // 加载每周和每月游玩时间以及相关图表
    loadPeriodStats(data);
}

// 新增函数：加载周期性统计数据和图表
function loadPeriodStats(data) {
    // 确保API请求绝对路径
    const baseUrl = window.location.origin;
    
    // 请求每日游玩时间数据
    fetch(`${baseUrl}/api/history`)
        .then(response => response.json())
        .then(historyData => {
            // 添加调试信息
            console.log('历史数据详情:', historyData);
            
            // 计算本周和本月游玩时间
            const now = new Date();
            
            // 计算本周开始日期（周日为一周的开始）
            const startOfWeek = new Date(now);
            startOfWeek.setDate(now.getDate() - now.getDay());
            startOfWeek.setHours(0, 0, 0, 0);
            
            // 计算本月开始日期
            const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
            
            // 初始化统计数据
            let weeklyMinutes = 0;
            let monthlyMinutes = 0;
            
            // 统计每一天的游玩时间
            historyData.forEach(day => {
                const dayDate = new Date(day.date);
                const totalMinutes = day.games ? day.games.reduce((sum, game) => sum + game.minutes, 0) : day.total_minutes || 0;
                
                // 统计本周时间
                if (dayDate >= startOfWeek) {
                    weeklyMinutes += totalMinutes;
                }
                
                // 统计本月时间
                if (dayDate >= startOfMonth) {
                    monthlyMinutes += totalMinutes;
                }
            });
            
            // 更新本周游玩时间
            const weeklyHours = Math.floor(weeklyMinutes / 60);
            const weeklyRemainingMinutes = weeklyMinutes % 60;
            document.getElementById('current-week-time').textContent = 
                `${weeklyHours}小时${weeklyRemainingMinutes > 0 ? weeklyRemainingMinutes + '分钟' : ''}`;
            
            // 更新本月游玩时间
            const monthlyHours = Math.floor(monthlyMinutes / 60);
            const monthlyRemainingMinutes = monthlyMinutes % 60;
            document.getElementById('current-month-time').textContent = 
                `${monthlyHours}小时${monthlyRemainingMinutes > 0 ? monthlyRemainingMinutes + '分钟' : ''}`;
            
            // 创建月度游玩时间图表
            createMonthlyChart(historyData);
            
            // 创建游玩时间最长的游戏图表
            createTopGamesChart(data.playHistories);
        })
        .catch(error => {
            console.error('加载统计数据失败:', error);
            // 提供默认值
            document.getElementById('current-week-time').textContent = '数据加载失败';
            document.getElementById('current-month-time').textContent = '数据加载失败';
        });
}

// 创建游玩时间分布图表
function createPlaytimeChart(games) {
    // 确保API请求绝对路径
    const baseUrl = window.location.origin;
    
    // 请求最近活动数据获取最近一周的游戏数据
    fetch(`${baseUrl}/api/recent_activities`)
        .then(response => response.json())
        .then(recentData => {
            // 添加调试日志
            console.log('最近游玩数据原始格式:', recentData);
            
            // 处理最近一周的游戏数据
            let recentGames = [];
            let gamePlaytimes = {};
            
            // 检查数据格式
            if (Array.isArray(recentData)) {
                // 标准格式：数组中包含每天的记录
                recentData.forEach(day => {
                    if (day.dailyPlayHistories && Array.isArray(day.dailyPlayHistories)) {
                        day.dailyPlayHistories.forEach(game => {
                            if (gamePlaytimes[game.titleId]) {
                                gamePlaytimes[game.titleId].totalPlayedMinutes += game.totalPlayedMinutes;
                            } else {
                                gamePlaytimes[game.titleId] = {
                                    titleId: game.titleId,
                                    titleName: game.titleName,
                                    imageUrl: game.imageUrl,
                                    totalPlayedMinutes: game.totalPlayedMinutes
                                };
                            }
                        });
                    }
                });
            } else if (recentData && recentData.recentPlayHistories && Array.isArray(recentData.recentPlayHistories)) {
                // 兼容旧格式
                recentData.recentPlayHistories.forEach(day => {
                    if (day.dailyPlayHistories && Array.isArray(day.dailyPlayHistories)) {
                        day.dailyPlayHistories.forEach(game => {
                            if (gamePlaytimes[game.titleId]) {
                                gamePlaytimes[game.titleId].totalPlayedMinutes += game.totalPlayedMinutes;
                            } else {
                                gamePlaytimes[game.titleId] = {
                                    titleId: game.titleId,
                                    titleName: game.titleName,
                                    imageUrl: game.imageUrl,
                                    totalPlayedMinutes: game.totalPlayedMinutes
                                };
                            }
                        });
                    }
                });
            }
            
            // 转换为数组并排序
            recentGames = Object.values(gamePlaytimes);
            
            console.log('处理后的游戏数据:', recentGames);
            
            // 检查是否有数据
            if (recentGames.length === 0) {
                console.log('没有找到最近游玩数据，使用全部游戏数据回退');
                fallbackToAllGamesChart(games);
                return;
            }
            
            // 按游玩时间排序
            recentGames.sort((a, b) => b.totalPlayedMinutes - a.totalPlayedMinutes);
            
            // 只取前5个游戏用于图表展示
            const topGames = recentGames.slice(0, 5);
            
            const ctx = document.getElementById('playtime-chart').getContext('2d');
            
            // 销毁已存在的图表
            if (window.playtimeChart) {
                window.playtimeChart.destroy();
            }
            
            // 获取游戏名和游戏时间
            const gameNames = topGames.map(game => {
                // 截断过长的游戏名，限制在12个字符
                let name = game.titleName;
                if (name.length > 12) {
                    name = name.substring(0, 12) + '...';
                }
                return name;
            });
            
            const gameTimes = topGames.map(game => Math.round(game.totalPlayedMinutes / 60 * 10) / 10);
            
            console.log('图表数据:', { gameNames, gameTimes });
            
            // 更改图表标题
            document.querySelector('.chart-wrapper h3').innerHTML = '<i class="fas fa-chart-pie"></i> 最近游玩时间分布';
            
            window.playtimeChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: gameNames,
                    datasets: [{
                        label: '游玩时间（小时）',
                        data: gameTimes,
                        backgroundColor: '#e60012', // Switch红色
                        borderColor: '#e60012',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    indexAxis: 'y',
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    // 在提示中显示完整游戏名
                                    const gameIndex = context[0].dataIndex;
                                    return topGames[gameIndex].titleName;
                                },
                                label: function(context) {
                                    const value = context.raw;
                                    const hours = Math.floor(value);
                                    const minutes = Math.round((value - hours) * 60);
                                    return `${hours}小时${minutes > 0 ? minutes + '分钟' : ''}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            grid: {
                                display: false
                            }
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('获取最近游玩数据失败:', error);
            
            // 失败时回退到使用所有游戏数据
            console.log('API请求失败，使用全部游戏数据回退');
            fallbackToAllGamesChart(games);
        });
}

// 添加回退方法，使用所有游戏数据
function fallbackToAllGamesChart(games) {
    console.log('执行回退方法，使用全部游戏数据');
    
    // 只取前5个游戏用于图表展示
    const topGames = [...games]
        .sort((a, b) => b.totalPlayedMinutes - a.totalPlayedMinutes)
        .slice(0, 5);
    
    const ctx = document.getElementById('playtime-chart').getContext('2d');
    
    // 销毁已存在的图表
    if (window.playtimeChart) {
        window.playtimeChart.destroy();
    }
    
    // 获取游戏名和游戏时间
    const gameNames = topGames.map(game => {
        // 截断过长的游戏名，限制在12个字符
        let name = game.titleName;
        if (name.length > 12) {
            name = name.substring(0, 12) + '...';
        }
        return name;
    });
    
    const gameTimes = topGames.map(game => Math.round(game.totalPlayedMinutes / 60 * 10) / 10);
    
    console.log('回退图表数据:', { gameNames, gameTimes });
    
    // 标题加上"(全部)"以区分
    document.querySelector('.chart-wrapper h3').innerHTML = '<i class="fas fa-chart-pie"></i> 最近游玩时间分布 (全部)';
    
    window.playtimeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: gameNames,
            datasets: [{
                label: '游玩时间（小时）',
                data: gameTimes,
                backgroundColor: '#e60012', // Switch红色
                borderColor: '#e60012',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            // 在提示中显示完整游戏名
                            const gameIndex = context[0].dataIndex;
                            return topGames[gameIndex].titleName;
                        },
                        label: function(context) {
                            const value = context.raw;
                            const hours = Math.floor(value);
                            const minutes = Math.round((value - hours) * 60);
                            return `${hours}小时${minutes > 0 ? minutes + '分钟' : ''}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// 更新最近活动
function updateRecentActivity(recentHistories) {
    const recentActivityContainer = document.getElementById('recent-activity');
    recentActivityContainer.innerHTML = '';
    
    if (!recentHistories || recentHistories.length === 0) {
        recentActivityContainer.innerHTML = '<div class="no-data">暂无最近活动</div>';
        return;
    }
    
    // 从API返回的数据格式分析
    console.log('最近活动数据结构:', recentHistories);
    
    // 检查数据结构是否是数组对象，每个对象有dailyPlayHistories属性
    const hasDailyPlayHistories = recentHistories.length > 0 && recentHistories[0].dailyPlayHistories;
    
    if (hasDailyPlayHistories) {
        // 旧格式数据处理：从各天记录中提取最近的游戏活动
        const recentGames = [];
        
        // 遍历每天的记录，提取所有游戏活动
        recentHistories.forEach(day => {
            if (day.dailyPlayHistories && day.dailyPlayHistories.length > 0) {
                day.dailyPlayHistories.forEach(game => {
                    recentGames.push({
                        titleName: game.titleName,
                        imageUrl: game.imageUrl,
                        playedMinutes: game.totalPlayedMinutes,
                        playedDate: day.playedDate
                    });
                });
            }
        });
        
        // 按日期排序，最近的在前
        recentGames.sort((a, b) => new Date(b.playedDate) - new Date(a.playedDate));
        
        // 只显示最近的8个活动
        const showCount = Math.min(8, recentGames.length);
        
        for (let i = 0; i < showCount; i++) {
            const game = recentGames[i];
            const date = new Date(game.playedDate);
            
            // 格式化日期显示
            const today = new Date();
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            
            let dateText = '';
            if (date.toDateString() === today.toDateString()) {
                dateText = '今天';
            } else if (date.toDateString() === yesterday.toDateString()) {
                dateText = '昨天';
            } else {
                dateText = `${date.getMonth() + 1}月${date.getDate()}日`;
            }
            
            // 创建活动项
            const activityItem = document.createElement('div');
            activityItem.className = 'activity-item';
            
            // 如果图片地址不是以http开头，添加基本URL
            let imageUrl = game.imageUrl;
            if (imageUrl && !imageUrl.startsWith('http')) {
                const baseUrl = window.location.origin;
                imageUrl = `${baseUrl}${imageUrl}`;
            }
            
            // 格式化时间显示
            const hours = Math.floor(game.playedMinutes / 60);
            const minutes = game.playedMinutes % 60;
            let timeDisplay = '';
            
            if (hours > 0) {
                timeDisplay += `${hours}小时`;
            }
            if (minutes > 0 || hours === 0) {
                timeDisplay += `${minutes}分钟`;
            }
            
            activityItem.innerHTML = `
                <img src="${imageUrl || 'https://placehold.co/100x100?text=游戏'}" alt="${game.titleName}" class="activity-image">
                <div class="activity-info">
                    <div class="activity-title">${game.titleName}</div>
                    <div class="activity-time">${timeDisplay} · ${dateText}</div>
                </div>
            `;
            
            recentActivityContainer.appendChild(activityItem);
        }
    } else {
        // 尝试处理可能的其他格式
        let activitiesToShow = [];
        
        if (Array.isArray(recentHistories)) {
            // 可能是直接的活动列表
            activitiesToShow = recentHistories.slice(0, 8);
        } else if (recentHistories.recentPlayHistories && Array.isArray(recentHistories.recentPlayHistories)) {
            // 可能是包装在对象中的活动列表
            activitiesToShow = recentHistories.recentPlayHistories.slice(0, 8);
        }
        
        if (activitiesToShow.length === 0) {
            recentActivityContainer.innerHTML = '<div class="no-data">暂无最近活动数据</div>';
            return;
        }
        
        // 遍历活动创建元素
        activitiesToShow.forEach(activity => {
            const activityItem = document.createElement('div');
            activityItem.className = 'activity-item';
            
            // 尝试确定日期
            let dateText = '未知日期';
            let date = null;
            
            if (activity.playTime) {
                date = new Date(activity.playTime);
            } else if (activity.playedDate) {
                date = new Date(activity.playedDate);
            } else if (activity.lastPlayedAt) {
                date = new Date(activity.lastPlayedAt);
            }
            
            if (date) {
                const today = new Date();
                const yesterday = new Date(today);
                yesterday.setDate(yesterday.getDate() - 1);
                
                if (date.toDateString() === today.toDateString()) {
                    dateText = '今天';
                } else if (date.toDateString() === yesterday.toDateString()) {
                    dateText = '昨天';
                } else {
                    dateText = `${date.getMonth() + 1}月${date.getDate()}日`;
                }
            }
            
            // 尝试获取图片URL
            let imageUrl = activity.imageUrl || activity.image_url || '';
            if (imageUrl && !imageUrl.startsWith('http')) {
                const baseUrl = window.location.origin;
                imageUrl = `${baseUrl}${imageUrl}`;
            }
            
            // 尝试获取游戏名称
            const gameName = activity.titleName || activity.name || '未知游戏';
            
            // 尝试获取游玩时间
            let playedMinutes = activity.playedMinutes || activity.totalPlayedMinutes || 0;
            const hours = Math.floor(playedMinutes / 60);
            const minutes = playedMinutes % 60;
            let timeDisplay = '';
            
            if (hours > 0) {
                timeDisplay += `${hours}小时`;
            }
            if (minutes > 0 || hours === 0) {
                timeDisplay += `${minutes}分钟`;
            }
            
            activityItem.innerHTML = `
                <img src="${imageUrl || 'https://placehold.co/100x100?text=游戏'}" alt="${gameName}" class="activity-image">
                <div class="activity-info">
                    <div class="activity-title">${gameName}</div>
                    <div class="activity-time">${timeDisplay || '未知时间'} · ${dateText}</div>
                </div>
            `;
            
            recentActivityContainer.appendChild(activityItem);
        });
    }
}

// 更新"最近"标签页
function updateRecentTab(recentHistories) {
    const recentTabContent = document.getElementById('recent-tab-content');
    recentTabContent.innerHTML = '';
    
    if (!recentHistories || recentHistories.length === 0) {
        recentTabContent.innerHTML = '<p class="no-data">暂无最近活动数据</p>';
        return;
    }
    
    // 去重处理：使用Map记录每个游戏在每天只显示一次
    const processedDays = new Map();
    
    recentHistories.forEach(day => {
        const dayElement = document.createElement('div');
        dayElement.className = 'recent-day';
        
        // 格式化日期
        const dateParts = day.playedDate.split('-');
        const formattedDate = `${dateParts[0]}年${parseInt(dateParts[1])}月${parseInt(dateParts[2])}日`;
        
        const totalMinutes = day.dailyPlayHistories.reduce((total, game) => total + game.totalPlayedMinutes, 0);
        const totalHours = Math.floor(totalMinutes / 60);
        const remainingMinutes = totalMinutes % 60;
        
        dayElement.innerHTML = `
            <div class="day-header">
                <h3>${formattedDate}</h3>
                <span class="day-total">共 ${totalHours}小时${remainingMinutes > 0 ? remainingMinutes + '分钟' : ''}</span>
            </div>
            <div class="day-games"></div>
        `;
        
        const gamesContainer = dayElement.querySelector('.day-games');
        
        // 按游戏时间排序
        const sortedGames = [...day.dailyPlayHistories].sort((a, b) => b.totalPlayedMinutes - a.totalPlayedMinutes);
        
        // 使用Set来记录已经显示过的游戏ID，防止重复
        const displayedGameIds = new Set();
        
        sortedGames.forEach(game => {
            // 如果这个游戏已经在当天显示过，则跳过
            if (displayedGameIds.has(game.titleId)) {
                return;
            }
            
            displayedGameIds.add(game.titleId);
            
            const gameHours = Math.floor(game.totalPlayedMinutes / 60);
            const gameMinutes = game.totalPlayedMinutes % 60;
            
            const gameElement = document.createElement('div');
            gameElement.className = 'recent-game';
            gameElement.innerHTML = `
                <img src="${game.imageUrl || 'assets/default-game.png'}" alt="${game.titleName}" onerror="this.src='assets/default-game.png'">
                <div class="game-details">
                    <h4>${game.titleName}</h4>
                    <p>${gameHours > 0 ? gameHours + '小时' : ''}${gameMinutes > 0 ? gameMinutes + '分钟' : (gameHours === 0 ? '不到1分钟' : '')}</p>
                </div>
            `;
            
            gamesContainer.appendChild(gameElement);
        });
        
        recentTabContent.appendChild(dayElement);
    });
}

// 创建游戏列表项
function createGameItem(game) {
    // 提取日期部分，例如：2023-04-15T12:34:56Z -> 2023-04-15
    const lastPlayedDate = game.lastPlayedAt ? game.lastPlayedAt.split('T')[0] : '';
    
    // 计算游玩时间文本
    const totalHours = Math.floor(game.totalPlayedMinutes / 60);
    const totalMinutes = game.totalPlayedMinutes % 60;
    const timeText = `${totalHours}小时${totalMinutes > 0 ? totalMinutes + '分钟' : ''}`;
    
    // 创建游戏卡片元素
    const gameItem = document.createElement('div');
    gameItem.className = 'game-card';
    
    // 设置游戏卡片内容
    gameItem.innerHTML = `
        <div class="game-card-header">
            <img src="${game.imageUrl || 'assets/default-game.png'}" alt="${game.titleName}" onerror="this.src='assets/default-game.png'">
        </div>
        <div class="game-card-body">
            <h4>${game.titleName}</h4>
            <p class="game-time">${timeText}</p>
            <p class="game-last-played">最后游玩: ${lastPlayedDate}</p>
        </div>
    `;
    
    return gameItem;
}

// 更新游戏列表
function updateGamesList(games) {
    const gamesGrid = document.getElementById('games-grid');
    
    // 清空当前游戏列表
    gamesGrid.innerHTML = '';
    
    // 默认按游玩时间排序
    const sortedGames = [...games].sort((a, b) => b.totalPlayedMinutes - a.totalPlayedMinutes);
    
    // 渲染游戏列表
    sortedGames.forEach(game => {
        const gameItem = createGameItem(game);
        gamesGrid.appendChild(gameItem);
    });
    
    // 保存为全局变量以便后续操作
    gameData = [...games];
}

// 游戏搜索过滤
function filterGames(searchTerm) {
    if (!gameData) return;
    
    // 如果搜索词为空，则显示所有游戏
    if (!searchTerm.trim()) {
        updateGamesList(gameData);
        return;
    }
    
    // 过滤游戏
    const filteredGames = gameData.filter(game => 
        game.titleName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (game.originalName && game.originalName.toLowerCase().includes(searchTerm.toLowerCase()))
    );
    
    // 更新游戏列表
    updateGamesList(filteredGames);
}

// 游戏排序
function sortGames(sortOption) {
    if (!gameData) return;
    
    let sortedGames;
    
    switch (sortOption) {
        case 'playtime':
            sortedGames = [...gameData].sort((a, b) => b.totalPlayedMinutes - a.totalPlayedMinutes);
            break;
        case 'recent':
            sortedGames = [...gameData].sort((a, b) => {
                // 确保日期字符串格式一致进行比较
                const dateA = a.lastPlayedAt ? new Date(a.lastPlayedAt) : new Date(0);
                const dateB = b.lastPlayedAt ? new Date(b.lastPlayedAt) : new Date(0);
                return dateB - dateA;
            });
            break;
        case 'name':
            sortedGames = [...gameData].sort((a, b) => a.titleName.localeCompare(b.titleName));
            break;
        default:
            sortedGames = [...gameData];
    }
    
    // 更新游戏列表显示
    const gamesGrid = document.getElementById('games-grid');
    gamesGrid.innerHTML = '';
    
    sortedGames.forEach(game => {
        const gameItem = createGameItem(game);
        gamesGrid.appendChild(gameItem);
    });
}

// 更新统计页面
function updateStatistics(data) {
    // 计算实际游戏总时长（只使用真实数据）
    const totalMinutes = data.playHistories.reduce((total, game) => total + game.totalPlayedMinutes, 0);
    const totalHours = Math.floor(totalMinutes / 60);
    const remainingMinutes = totalMinutes % 60;
    
    // 设置总游玩时间
    document.getElementById('total-game-time').textContent = `${totalHours}小时${remainingMinutes > 0 ? remainingMinutes + '分钟' : ''}`;
    
    // 统计游戏总数
    document.getElementById('games-count').textContent = `${data.playHistories.length}款`;
    
    // 计算本周游戏时间（基于API数据）
    const baseUrl = window.location.origin;
    
    // 请求每日游玩时间数据，计算本周时间
    fetch(`${baseUrl}/api/history`)
        .then(response => response.json())
        .then(historyData => {
            // 计算本周和本月游玩时间
            const now = new Date();
            const startOfWeek = new Date(now);
            startOfWeek.setDate(now.getDate() - now.getDay()); // 设置为本周日
            startOfWeek.setHours(0, 0, 0, 0);
            
            const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
            
            // 计算本周游戏时间
            let weeklyMinutes = 0;
            let monthlyMinutes = 0;
            
            historyData.forEach(day => {
                const dayDate = new Date(day.date);
                
                // 统计本周时间
                if (dayDate >= startOfWeek) {
                    weeklyMinutes += day.total_minutes || 0;
                }
                
                // 统计本月时间
                if (dayDate >= startOfMonth) {
                    monthlyMinutes += day.total_minutes || 0;
                }
            });
            
            // 更新UI
            const weeklyHours = Math.floor(weeklyMinutes / 60);
            const weeklyRemainingMinutes = weeklyMinutes % 60;
            document.getElementById('current-week-time').textContent = 
                `${weeklyHours}小时${weeklyRemainingMinutes > 0 ? weeklyRemainingMinutes + '分钟' : ''}`;
            
            const monthlyHours = Math.floor(monthlyMinutes / 60);
            const monthlyRemainingMinutes = monthlyMinutes % 60;
            document.getElementById('current-month-time').textContent = 
                `${monthlyHours}小时${monthlyRemainingMinutes > 0 ? monthlyRemainingMinutes + '分钟' : ''}`;
            
            // 创建月度游玩时间图表
            createMonthlyChart(historyData);
            
            // 创建游玩时间最长的游戏图表
            createTopGamesChart(data.playHistories);
            
            // 创建游戏里程碑
            createGameMilestones(data.playHistories);
        })
        .catch(error => {
            console.error('获取历史数据失败:', error);
        });
}

// 修改createMonthlyChart函数，解决图表显示问题
function createMonthlyChart(games) {
    // 仅从API获取实际数据，不使用估算
    const baseUrl = window.location.origin;
    fetch(`${baseUrl}/api/monthly_playtime`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(monthlyData => {
            console.log('月度数据加载成功:', monthlyData);
            
            // 获取所有月份并排序
            const sortedMonths = Object.keys(monthlyData).sort();
            
            // 只保留最近12个月的数据，避免图表过长
            const recentMonths = sortedMonths.slice(-12);
            
            // 销毁已存在的图表
            if (window.monthlyChart) {
                window.monthlyChart.destroy();
            }
            
            // 计算每月的小时数
            const hourlyData = recentMonths.map(month => Math.round(monthlyData[month] / 60 * 10) / 10);
            
            // 创建图表
            const ctx = document.getElementById('monthly-chart').getContext('2d');
            window.monthlyChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: recentMonths.map(month => {
                        const [year, monthNum] = month.split('-');
                        return `${year}年${parseInt(monthNum)}月`;
                    }),
                    datasets: [{
                        type: 'bar',
                        label: '游玩时间（小时）',
                        data: hourlyData,
                        backgroundColor: 'rgba(0, 133, 199, 0.7)', // Switch蓝色
                        borderColor: 'rgba(0, 133, 199, 1)',
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `游玩时间: ${context.raw}小时`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    size: 11
                                },
                                maxRotation: 45,
                                minRotation: 45
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.05)'
                            },
                            ticks: {
                                font: {
                                    size: 12
                                },
                                callback: function(value) {
                                    return value + '小时';
                                }
                            }
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('加载月度游玩时间数据失败:', error);
            
            // 显示错误信息
            const ctx = document.getElementById('monthly-chart').getContext('2d');
            ctx.font = '14px Arial';
            ctx.fillStyle = '#666';
            ctx.textAlign = 'center';
            ctx.fillText('月度数据加载失败', ctx.canvas.width / 2, ctx.canvas.height / 2);
        });
}

// 创建游戏里程碑
function createGameMilestones(games) {
    const milestonesContainer = document.getElementById('game-milestones');
    milestonesContainer.innerHTML = ''; // 清除现有内容
    
    // 计算里程碑
    const milestones = [];
    
    // 总游戏时长里程碑
    const totalMinutes = games.reduce((total, game) => total + game.totalPlayedMinutes, 0);
    const totalHours = Math.floor(totalMinutes / 60);
    
    milestones.push({
        icon: 'fa-clock',
        title: '游戏时间达人',
        description: `总游戏时间达到${totalHours}小时`
    });
    
    // 游戏数量里程碑
    const gamesCount = games.length;
    milestones.push({
        icon: 'fa-gamepad',
        title: '游戏收藏家',
        description: `已游玩${gamesCount}款不同游戏`
    });
    
    // 最常玩的游戏里程碑
    if (games.length > 0) {
        const mostPlayedGame = games.reduce((prev, current) => 
            (prev.totalPlayedMinutes > current.totalPlayedMinutes) ? prev : current
        );
        
        const mostPlayedHours = Math.floor(mostPlayedGame.totalPlayedMinutes / 60);
        milestones.push({
            icon: 'fa-star',
            title: '忠实粉丝',
            description: `《${mostPlayedGame.titleName}》游玩${mostPlayedHours}小时`
        });
    }
    
    // 其他自定义里程碑
    // 连续游玩里程碑
    const consecutiveDays = calculateConsecutiveDays(games);
    if (consecutiveDays > 1) {
        milestones.push({
            icon: 'fa-calendar-check',
            title: '持之以恒',
            description: `连续${consecutiveDays}天游玩Switch`
        });
    }
    
    // 渲染里程碑
    milestones.forEach(milestone => {
        const milestoneElement = document.createElement('div');
        milestoneElement.className = 'milestone-card';
        milestoneElement.innerHTML = `
            <div class="milestone-icon">
                <i class="fas ${milestone.icon}"></i>
            </div>
            <div class="milestone-info">
                <h4>${milestone.title}</h4>
                <p>${milestone.description}</p>
            </div>
        `;
        milestonesContainer.appendChild(milestoneElement);
    });
}

// 计算连续游玩天数
function calculateConsecutiveDays(games) {
    // 获取所有游玩日期
    const playDates = new Set();
    
    games.forEach(game => {
        if (game.lastPlayedAt) {
            const lastPlayed = new Date(game.lastPlayedAt);
            playDates.add(lastPlayed.toISOString().split('T')[0]);
        }
    });
    
    // 简化实现：检查最近的几天是否连续游玩
    // 实际应该基于更详细的历史数据
    const sortedDates = Array.from(playDates).sort();
    let maxConsecutive = 1;
    let currentConsecutive = 1;
    
    for (let i = 1; i < sortedDates.length; i++) {
        const prevDate = new Date(sortedDates[i-1]);
        const currDate = new Date(sortedDates[i]);
        
        // 检查是否是连续的两天
        const dayDiff = (currDate - prevDate) / (1000 * 60 * 60 * 24);
        
        if (dayDiff === 1) {
            currentConsecutive++;
            maxConsecutive = Math.max(maxConsecutive, currentConsecutive);
        } else {
            currentConsecutive = 1;
        }
    }
    
    return maxConsecutive;
}

// 修改createTopGamesChart函数，改善布局和显示效果
function createTopGamesChart(games) {
    // 只取前8个游戏
    const topGames = [...games]
        .sort((a, b) => b.totalPlayedMinutes - a.totalPlayedMinutes)
        .slice(0, 8);
    
    const ctx = document.getElementById('top-games-chart').getContext('2d');
    
    // 销毁已存在的图表
    if (window.topGamesChart) {
        window.topGamesChart.destroy();
    }
    
    // 准备数据
    const gameNames = topGames.map(game => {
        let name = game.titleName;
        if (name.length > 15) {
            name = name.substring(0, 15) + '...';
        }
        return name;
    });
    
    const gameTimes = topGames.map(game => Math.round(game.totalPlayedMinutes / 60 * 10) / 10);
    
    // 创建图表
    window.topGamesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: gameNames,
            datasets: [{
                label: '游玩时间（小时）',
                data: gameTimes,
                backgroundColor: topGames.map((_, index) => {
                    // 为每个条形生成不同的颜色
                    if (index === 0) return 'rgba(230, 0, 18, 0.85)'; // Switch红色 (第一名)
                    if (index === 1) return 'rgba(0, 133, 199, 0.85)'; // Switch蓝色 (第二名)
                    if (index === 2) return 'rgba(255, 186, 8, 0.85)'; // Switch黄色 (第三名)
                    if (index < 5) return 'rgba(111, 195, 224, 0.85)'; // 浅蓝色
                    return 'rgba(153, 153, 153, 0.75)'; // 灰色
                }),
                borderColor: topGames.map((_, index) => {
                    if (index === 0) return 'rgba(230, 0, 18, 1)'; 
                    if (index === 1) return 'rgba(0, 133, 199, 1)';
                    if (index === 2) return 'rgba(255, 186, 8, 1)';
                    if (index < 5) return 'rgba(111, 195, 224, 1)';
                    return 'rgba(153, 153, 153, 1)';
                }),
                borderWidth: 1,
                borderRadius: 6,
                barPercentage: 0.7
            }]
        },
        options: {
            indexAxis: 'y',  // 水平条形图
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            return `游玩时间: ${value}小时`;
                        },
                        afterLabel: function(context) {
                            const game = topGames[context.dataIndex];
                            const totalDays = game.totalPlayedDays;
                            return `游玩${totalDays}天 | 平均每天${Math.round(game.totalPlayedMinutes / totalDays / 60 * 10) / 10}小时`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            size: 12
                        },
                        callback: function(value) {
                            return value + '小时';
                        }
                    }
                },
                y: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            size: 12,
                            weight: 'bold'
                        },
                        color: 'rgba(0, 0, 0, 0.7)'
                    }
                }
            }
        }
    });
}

// 当前显示的日历年月
let currentCalendarDate = new Date();

// 初始化游戏日历
function initGameCalendar() {
    renderCalendar(currentCalendarDate);
    loadDailyPlayData();
}

// 渲染日历
function renderCalendar(date) {
    const year = date.getFullYear();
    const month = date.getMonth();
    
    // 更新日历标题
    document.getElementById('calendar-title').textContent = `${year}年${month + 1}月`;
    
    // 获取当前月的第一天
    const firstDayOfMonth = new Date(year, month, 1);
    // 获取当前月的最后一天
    const lastDayOfMonth = new Date(year, month + 1, 0);
    
    // 获取第一天是星期几（0是星期日，6是星期六）
    const firstDayOfWeek = firstDayOfMonth.getDay();
    
    // 获取当前月的天数
    const daysInMonth = lastDayOfMonth.getDate();
    
    // 获取上个月的最后几天（用于填充日历的第一行）
    const lastDayOfPrevMonth = new Date(year, month, 0).getDate();
    
    // 清空日历网格
    const calendarGrid = document.getElementById('calendar-grid');
    calendarGrid.innerHTML = '';
    
    // 添加上个月的日期（需要填充的天数）
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
        const day = lastDayOfPrevMonth - i;
        const prevMonthDate = new Date(year, month - 1, day);
        const dateString = prevMonthDate.toISOString().split('T')[0];
        
        const dayElement = document.createElement('div');
        dayElement.className = 'calendar-day outside-month';
        dayElement.innerHTML = `
            <div class="day-number">${day}</div>
            <div class="day-hours" data-date="${dateString}">--</div>
        `;
        
        calendarGrid.appendChild(dayElement);
    }
    
    // 添加当前月的日期
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    for (let day = 1; day <= daysInMonth; day++) {
        const currentDate = new Date(year, month, day);
        const dateString = currentDate.toISOString().split('T')[0];
        const isToday = currentDate.getTime() === today.getTime();
        
        const dayElement = document.createElement('div');
        dayElement.className = `calendar-day${isToday ? ' today' : ''}`;
        dayElement.dataset.date = dateString;
        dayElement.innerHTML = `
            <div class="day-number">${day}</div>
            <div class="day-hours" data-date="${dateString}">--</div>
        `;
        
        // 添加点击事件
        dayElement.addEventListener('click', function() {
            // 移除其他日期的active类
            document.querySelectorAll('.calendar-day.active').forEach(el => {
                el.classList.remove('active');
            });
            
            // 添加active类到当前点击的日期
            dayElement.classList.add('active');
            
            // 显示当天的游戏详情
            showDayDetails(dateString);
        });
        
        calendarGrid.appendChild(dayElement);
    }
    
    // 计算需要添加的下个月的天数（填充到6行7列）
    const totalCells = 42;
    const remainingCells = totalCells - (firstDayOfWeek + daysInMonth);
    
    // 添加下个月的日期
    for (let day = 1; day <= remainingCells; day++) {
        const nextMonthDate = new Date(year, month + 1, day);
        const dateString = nextMonthDate.toISOString().split('T')[0];
        
        const dayElement = document.createElement('div');
        dayElement.className = 'calendar-day outside-month';
        dayElement.innerHTML = `
            <div class="day-number">${day}</div>
            <div class="day-hours" data-date="${dateString}">--</div>
        `;
        
        calendarGrid.appendChild(dayElement);
    }
}

// 导航日历
function navigateCalendar(months) {
    currentCalendarDate.setMonth(currentCalendarDate.getMonth() + months);
    renderCalendar(currentCalendarDate);
    loadDailyPlayData();
}

// 加载每日游玩数据
function loadDailyPlayData() {
    const baseUrl = window.location.origin;
    
    // 获取每日历史数据
    fetch(`${baseUrl}/api/history`)
        .then(response => response.json())
        .then(historyData => {
            // 添加调试信息
            console.log('历史数据:', historyData);
            
            // 清空日历上的游玩时间
            document.querySelectorAll('.day-hours').forEach(el => {
                el.textContent = '--';
                el.parentElement.style.background = 'rgba(220, 220, 220, 0.5)';
            });
            
            // 修复日期格式问题：API返回的日期格式是带时间的ISO字符串
            // 更新日历上的游玩时间
            historyData.forEach(day => {
                // 提取日期部分 (YYYY-MM-DD)
                const dateString = day.date.split('T')[0];
                console.log('处理日期:', dateString);
                
                const hourElements = document.querySelectorAll(`.day-hours[data-date="${dateString}"]`);
                console.log(`找到${hourElements.length}个匹配元素`);
                
                // 计算当天总游玩分钟数
                let totalMinutes = 0;
                day.games.forEach(game => {
                    totalMinutes += game.minutes;
                });
                
                // 转换为小时
                const hours = Math.floor(totalMinutes / 60);
                const minutes = totalMinutes % 60;
                const timeText = hours > 0 ? 
                    `${hours}时${minutes > 0 ? minutes + '分' : ''}` : 
                    `${minutes}分钟`;
                
                // 更新日历单元格
                hourElements.forEach(el => {
                    el.textContent = timeText;
                    
                    // 设置颜色深浅
                    const dayElement = el.parentElement;
                    if (hours < 1) {
                        dayElement.style.background = 'rgba(75, 192, 192, 0.3)';
                    } else if (hours < 2) {
                        dayElement.style.background = 'rgba(75, 192, 192, 0.5)';
                    } else if (hours < 3) {
                        dayElement.style.background = 'rgba(75, 192, 192, 0.7)';
                    } else {
                        dayElement.style.background = 'rgba(75, 192, 192, 0.9)';
                    }
                });
            });
            
            // 如果当前月份有数据，默认选中今天或第一个有数据的日期
            const today = new Date().toISOString().split('T')[0];
            const todayElement = document.querySelector(`.calendar-day[data-date="${today}"]`);
            
            if (todayElement && todayElement.querySelector('.day-hours').textContent !== '--') {
                todayElement.click();
            } else {
                // 找到第一个有数据的日期（修复日期格式问题）
                const firstDataDay = historyData[0]?.date.split('T')[0];
                if (firstDataDay) {
                    const firstDataElement = document.querySelector(`.calendar-day[data-date="${firstDataDay}"]`);
                    console.log('选择日期元素:', firstDataDay, firstDataElement);
                    if (firstDataElement) {
                        firstDataElement.click();
                    }
                }
            }
        })
        .catch(error => {
            console.error('加载每日游玩数据失败:', error);
        });
}

// 显示特定日期的游戏详情
function showDayDetails(dateString) {
    const baseUrl = window.location.origin;
    const detailDate = document.getElementById('detail-date');
    const detailGames = document.getElementById('detail-games');
    
    // 格式化日期
    const date = new Date(dateString);
    const formattedDate = `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
    detailDate.textContent = `${formattedDate}的游戏记录`;
    
    // 清空游戏列表
    detailGames.innerHTML = '';
    
    // 加载指定日期的游戏数据
    fetch(`${baseUrl}/api/history`)
        .then(response => response.json())
        .then(historyData => {
            // 查找对应日期的数据（修复日期格式问题）
            const dayData = historyData.find(day => day.date.split('T')[0] === dateString);
            
            if (!dayData || !dayData.games || dayData.games.length === 0) {
                detailGames.innerHTML = '<div class="no-games-message">当日无游戏记录</div>';
                return;
            }
            
            // 合并相同游戏的记录（按title_id分组并累加游玩时间）
            const gameMap = new Map();
            
            dayData.games.forEach(game => {
                const key = game.title_id || game.name; // 如果没有title_id，使用name作为key
                
                if (gameMap.has(key)) {
                    // 已有相同游戏，累加游玩时间
                    const existingGame = gameMap.get(key);
                    existingGame.minutes += game.minutes;
                } else {
                    // 添加新游戏
                    gameMap.set(key, {...game});
                }
            });
            
            // 将Map转换回数组并按游玩时间排序
            const mergedGames = Array.from(gameMap.values())
                .sort((a, b) => b.minutes - a.minutes);
            
            // 显示游戏列表（使用合并后的数据）
            mergedGames.forEach(game => {
                const hours = Math.floor(game.minutes / 60);
                const minutes = game.minutes % 60;
                const timeText = hours > 0 ? 
                    `${hours}小时${minutes > 0 ? minutes + '分钟' : ''}` : 
                    `${minutes}分钟`;
                
                const gameElement = document.createElement('div');
                gameElement.className = 'detail-game-item';
                gameElement.innerHTML = `
                    <img src="${game.image_url || 'https://placehold.co/60x60?text=游戏'}" 
                         alt="${game.name}" 
                         class="detail-game-image"
                         onerror="this.src='https://placehold.co/60x60?text=游戏'">
                    <div class="detail-game-info">
                        <div class="detail-game-title">${game.name}</div>
                        <div class="detail-game-time">游玩时间: ${timeText}</div>
                    </div>
                `;
                
                detailGames.appendChild(gameElement);
            });
        })
        .catch(error => {
            console.error('加载日期详情失败:', error);
            detailGames.innerHTML = '<div class="no-games-message">数据加载失败</div>';
    });
} 
