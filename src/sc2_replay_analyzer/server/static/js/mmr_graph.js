// MMR Graph Overlay - Professional esports design with adaptive scaling
let chart = null;

// Configuration constants
const ADAPTIVE_PADDING_PERCENT = 0.18;
const MIN_Y_RANGE = 200;
const REFRESH_INTERVAL_MS = 30000;
const MMR_MIN_VALID = 2000;
const MMR_MAX_VALID = 8000;

async function fetchData() {
    const response = await fetch('/api/v1/mmr/history');
    const json = await response.json();
    // Filter out invalid MMR values (outliers, placement games, etc.)
    const data = json.data.filter(d => d.mmr >= MMR_MIN_VALID && d.mmr <= MMR_MAX_VALID);
    return {
        playerName: json.player_name || 'Player',
        data: data
    };
}

function calculateStats(data) {
    if (!data || data.length === 0) {
        return {
            currentMMR: 0,
            sessionDelta: 0,
            winRate: 0,
            wins: 0,
            losses: 0
        };
    }

    const currentMMR = data[data.length - 1].mmr;
    const sessionStartMMR = data[0].mmr;
    const sessionDelta = currentMMR - sessionStartMMR;

    const wins = data.filter(d => d.result === 'Win').length;
    const losses = data.filter(d => d.result === 'Loss').length;
    const totalGames = wins + losses;
    const winRate = totalGames > 0 ? (wins / totalGames) * 100 : 0;

    return {
        currentMMR,
        sessionDelta,
        winRate: Math.round(winRate),
        wins,
        losses
    };
}

function calculateAdaptiveYAxis(data) {
    if (!data || data.length === 0) {
        return { min: 0, max: 5000 };
    }

    const mmrValues = data.map(d => d.mmr);
    const minMMR = Math.min(...mmrValues);
    const maxMMR = Math.max(...mmrValues);
    const range = maxMMR - minMMR;

    const effectiveRange = Math.max(range, MIN_Y_RANGE);
    const padding = effectiveRange * ADAPTIVE_PADDING_PERCENT;

    const suggestedMin = Math.floor((minMMR - padding) / 50) * 50;
    const suggestedMax = Math.ceil((maxMMR + padding) / 50) * 50;

    return {
        min: suggestedMin,
        max: suggestedMax
    };
}

function updateTitle(playerName, gameCount) {
    const titleEl = document.querySelector('.title');
    titleEl.textContent = `${playerName}'s MMR (Last ${gameCount} games)`;
}

function updateStatsDisplay(stats, gameCount) {
    const currentMMREl = document.getElementById('currentMMR');
    const mmrDeltaEl = document.getElementById('mmrDelta');
    const winRateEl = document.getElementById('winRate');
    const deltaLabelEl = document.getElementById('deltaLabel');

    currentMMREl.textContent = stats.currentMMR.toLocaleString();

    // Update delta label to show actual game count
    deltaLabelEl.textContent = `LAST ${gameCount}`;

    const deltaPrefix = stats.sessionDelta > 0 ? '+' : '';
    mmrDeltaEl.textContent = `${deltaPrefix}${stats.sessionDelta}`;
    mmrDeltaEl.className = 'stat-value';
    if (stats.sessionDelta > 0) {
        mmrDeltaEl.classList.add('positive');
    } else if (stats.sessionDelta < 0) {
        mmrDeltaEl.classList.add('negative');
    } else {
        mmrDeltaEl.classList.add('neutral');
    }

    winRateEl.textContent = `${stats.winRate}%`;
}

async function initChart() {
    const result = await fetchData();
    const data = result.data;
    const stats = calculateStats(data);
    const yAxis = calculateAdaptiveYAxis(data);

    updateTitle(result.playerName, data.length);
    updateStatsDisplay(stats, data.length);

    const ctx = document.getElementById('mmrChart').getContext('2d');

    const gameLabels = data.map((_, index) => index + 1);

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: gameLabels,
            datasets: [{
                label: 'MMR',
                data: data.map(d => d.mmr),
                borderColor: '#ff9d5c',
                borderWidth: 3,
                backgroundColor: function(context) {
                    const chart = context.chart;
                    const {ctx, chartArea} = chart;
                    if (!chartArea) return null;

                    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                    gradient.addColorStop(0, 'rgba(255, 157, 92, 0.25)');
                    gradient.addColorStop(0.5, 'rgba(255, 120, 60, 0.12)');
                    gradient.addColorStop(1, 'rgba(255, 120, 60, 0.02)');
                    return gradient;
                },
                pointBackgroundColor: data.map(d =>
                    d.result === 'Win' ? '#00ff88' : '#ff4444'
                ),
                pointBorderColor: data.map(d =>
                    d.result === 'Win' ? '#00ff88' : '#ff4444'
                ),
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBorderWidth: 2,
                tension: 0.3,
                fill: true,
                shadowOffsetX: 0,
                shadowOffsetY: 0,
                shadowBlur: 10,
                shadowColor: 'rgba(255, 120, 60, 0.5)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(20, 25, 35, 0.95)',
                    titleColor: '#ff9d5c',
                    bodyColor: '#ffffff',
                    borderColor: 'rgba(255, 120, 60, 0.5)',
                    borderWidth: 2,
                    padding: 12,
                    displayColors: false,
                    titleFont: {
                        family: 'Rajdhani',
                        size: 14,
                        weight: 'bold'
                    },
                    bodyFont: {
                        family: 'Roboto Mono',
                        size: 13
                    },
                    callbacks: {
                        title: function(context) {
                            const dataIndex = context[0].dataIndex;
                            return `Game ${dataIndex + 1} - ${data[dataIndex].result}`;
                        },
                        label: function(context) {
                            return `MMR: ${context.parsed.y}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.7)',
                        font: {
                            family: 'Rajdhani',
                            size: 11,
                            weight: '600'
                        },
                        maxTicksLimit: 6,
                        callback: function(value, index) {
                            if (index === 0 || value % 20 === 0) {
                                return value;
                            }
                            return null;
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.06)',
                        drawBorder: false
                    },
                    border: {
                        display: false
                    }
                },
                y: {
                    display: true,
                    min: yAxis.min,
                    max: yAxis.max,
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.8)',
                        font: {
                            family: 'Roboto Mono',
                            size: 12,
                            weight: '600'
                        },
                        padding: 8,
                        callback: function(value) {
                            return value.toLocaleString();
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.08)',
                        drawBorder: false
                    },
                    border: {
                        display: false
                    }
                }
            },
            animation: {
                duration: 750,
                easing: 'easeInOutQuart'
            }
        }
    });
}

async function updateChart() {
    const result = await fetchData();
    const data = result.data;
    const stats = calculateStats(data);
    const yAxis = calculateAdaptiveYAxis(data);

    updateTitle(result.playerName, data.length);
    updateStatsDisplay(stats, data.length);

    const gameLabels = data.map((_, index) => index + 1);

    chart.data.labels = gameLabels;
    chart.data.datasets[0].data = data.map(d => d.mmr);
    chart.data.datasets[0].pointBackgroundColor = data.map(d =>
        d.result === 'Win' ? '#00ff88' : '#ff4444'
    );
    chart.data.datasets[0].pointBorderColor = data.map(d =>
        d.result === 'Win' ? '#00ff88' : '#ff4444'
    );

    chart.options.scales.y.min = yAxis.min;
    chart.options.scales.y.max = yAxis.max;

    chart.update('none');
}

initChart();
setInterval(updateChart, REFRESH_INTERVAL_MS);
