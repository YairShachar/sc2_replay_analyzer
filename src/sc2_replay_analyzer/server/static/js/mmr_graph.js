// MMR Graph Overlay - Professional esports design with adaptive scaling
let chart = null;

// Configuration constants
const ADAPTIVE_PADDING_PERCENT = 0.18;
const MIN_Y_RANGE = 200;
const REFRESH_INTERVAL_MS = 30000;
const MMR_MIN_VALID = 2000;
const MMR_MAX_VALID = 8000;

// Tag colors (must match Python TAG_COLORS)
const TAG_COLORS = [
    "#00d4ff",  // cyan
    "#b966ff",  // purple
    "#ffd700",  // yellow
    "#ff6bcd",  // pink
    "#00ffc8",  // teal
    "#6b9dff",  // blue
];

function getTagColor(label) {
    // Simple hash function for deterministic color assignment
    let hash = 0;
    for (let i = 0; i < label.length; i++) {
        const char = label.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length];
}

async function fetchData() {
    const response = await fetch('/api/v1/mmr/history');
    const json = await response.json();
    // Filter out invalid MMR values (outliers, placement games, etc.)
    const data = json.data.filter(d => d.mmr >= MMR_MIN_VALID && d.mmr <= MMR_MAX_VALID);
    return {
        playerName: json.player_name || 'Player',
        data: data,
        tags: json.tags || []
    };
}

function renderTagLegend(tags) {
    const legendEl = document.getElementById('tagLegend');
    if (!tags || tags.length === 0) {
        legendEl.innerHTML = '';
        return;
    }

    // Build legend HTML with icon-based grammar
    let html = '';
    tags.forEach(tag => {
        const color = getTagColor(tag.label);
        let icon;
        switch (tag.type) {
            case 'ongoing':
                icon = `<span class="tag-icon" style="color: ${color}">▸</span>`;
                break;
            case 'range':
                icon = `<span class="tag-icon" style="color: ${color}">◆─◆</span>`;
                break;
            default: // single
                icon = `<span class="tag-icon" style="color: ${color}">◆</span>`;
        }
        html += `<div class="tag-item">${icon}<span class="tag-label">${tag.label}</span></div>`;
    });

    legendEl.innerHTML = html;
}

function findTagPositions(data, tags) {
    // Find data point indices for each tag (start and end)
    // Returns array of {type, label, color, startIndex, endIndex}
    if (!tags || tags.length === 0) return [];

    // Build a map of date -> index for quick lookup
    const dateToIndex = {};
    data.forEach((d, index) => {
        const dateStr = d.date.substring(0, 10);
        // Store first occurrence (oldest) for start, last for end
        if (dateToIndex[dateStr] === undefined) {
            dateToIndex[dateStr] = { first: index, last: index };
        } else {
            dateToIndex[dateStr].last = index;
        }
    });

    const positions = [];
    const lastIndex = data.length - 1;

    tags.forEach(tag => {
        const color = getTagColor(tag.label);
        const startInfo = dateToIndex[tag.start_date];

        if (tag.type === 'single') {
            // Single date tag - just need one index
            if (startInfo) {
                positions.push({
                    type: 'single',
                    label: tag.label,
                    color: color,
                    startIndex: startInfo.first,
                    endIndex: startInfo.first
                });
            }
        } else if (tag.type === 'range') {
            // Completed range - need start and end
            const endInfo = dateToIndex[tag.end_date];
            if (startInfo || endInfo) {
                positions.push({
                    type: 'range',
                    label: tag.label,
                    color: color,
                    startIndex: startInfo ? startInfo.first : 0,
                    endIndex: endInfo ? endInfo.last : lastIndex
                });
            }
        } else if (tag.type === 'ongoing') {
            // Ongoing - start to current (end of data)
            if (startInfo) {
                positions.push({
                    type: 'ongoing',
                    label: tag.label,
                    color: color,
                    startIndex: startInfo.first,
                    endIndex: lastIndex
                });
            } else {
                // Tag starts before visible data - show full range
                positions.push({
                    type: 'ongoing',
                    label: tag.label,
                    color: color,
                    startIndex: 0,
                    endIndex: lastIndex
                });
            }
        }
    });

    return positions;
}

// Chart.js plugin to draw tag visualizations
const tagLinesPlugin = {
    id: 'tagLines',
    beforeDatasetsDraw(chart) {
        // Draw range/ongoing backgrounds BEFORE the data (so they appear behind)
        const pluginOptions = chart.options.plugins.tagLines || {};
        const tagPositions = pluginOptions.tagPositions || [];
        if (tagPositions.length === 0) return;

        const { ctx, chartArea, scales } = chart;
        const xScale = scales.x;

        ctx.save();

        // Draw range backgrounds first (behind everything)
        tagPositions.forEach(pos => {
            if (pos.type === 'range' || pos.type === 'ongoing') {
                const startX = xScale.getPixelForValue(pos.startIndex);
                const endX = xScale.getPixelForValue(pos.endIndex);

                // Parse color for rgba
                const baseColor = pos.color;

                if (pos.type === 'range') {
                    // Completed range: solid semi-transparent band
                    ctx.fillStyle = hexToRgba(baseColor, 0.12);
                    ctx.fillRect(startX, chartArea.top, endX - startX, chartArea.bottom - chartArea.top);
                } else {
                    // Ongoing: gradient fade-out
                    const gradient = ctx.createLinearGradient(startX, 0, chartArea.right, 0);
                    gradient.addColorStop(0, hexToRgba(baseColor, 0.15));
                    gradient.addColorStop(0.7, hexToRgba(baseColor, 0.06));
                    gradient.addColorStop(1, hexToRgba(baseColor, 0));
                    ctx.fillStyle = gradient;
                    ctx.fillRect(startX, chartArea.top, chartArea.right - startX, chartArea.bottom - chartArea.top);
                }
            }
        });

        ctx.restore();
    },

    afterDatasetsDraw(chart) {
        // Draw lines and markers AFTER the data
        const pluginOptions = chart.options.plugins.tagLines || {};
        const tagPositions = pluginOptions.tagPositions || [];
        if (tagPositions.length === 0) return;

        const { ctx, chartArea, scales } = chart;
        const xScale = scales.x;

        ctx.save();

        tagPositions.forEach(pos => {
            const startX = xScale.getPixelForValue(pos.startIndex);
            const endX = xScale.getPixelForValue(pos.endIndex);

            if (pos.type === 'single') {
                // Single date: dashed vertical line + diamond
                ctx.beginPath();
                ctx.setLineDash([4, 4]);
                ctx.strokeStyle = pos.color;
                ctx.lineWidth = 1.5;
                ctx.globalAlpha = 0.7;
                ctx.moveTo(startX, chartArea.top);
                ctx.lineTo(startX, chartArea.bottom);
                ctx.stroke();

                // Diamond at bottom
                ctx.setLineDash([]);
                ctx.globalAlpha = 1;
                ctx.fillStyle = pos.color;
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('◆', startX, chartArea.bottom + 12);

            } else if (pos.type === 'range') {
                // Completed range: solid edge lines + diamonds at both ends
                ctx.setLineDash([]);
                ctx.strokeStyle = pos.color;
                ctx.lineWidth = 2;
                ctx.globalAlpha = 0.6;

                // Left edge
                ctx.beginPath();
                ctx.moveTo(startX, chartArea.top);
                ctx.lineTo(startX, chartArea.bottom);
                ctx.stroke();

                // Right edge
                ctx.beginPath();
                ctx.moveTo(endX, chartArea.top);
                ctx.lineTo(endX, chartArea.bottom);
                ctx.stroke();

                // Diamonds at bottom
                ctx.globalAlpha = 1;
                ctx.fillStyle = pos.color;
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('◆', startX, chartArea.bottom + 12);
                ctx.fillText('◆', endX, chartArea.bottom + 12);

            } else if (pos.type === 'ongoing') {
                // Ongoing: dashed left edge + arrow indicator
                ctx.setLineDash([4, 4]);
                ctx.strokeStyle = pos.color;
                ctx.lineWidth = 2;
                ctx.globalAlpha = 0.6;

                // Left edge (dashed)
                ctx.beginPath();
                ctx.moveTo(startX, chartArea.top);
                ctx.lineTo(startX, chartArea.bottom);
                ctx.stroke();

                // Arrow marker at bottom (pointing right)
                ctx.setLineDash([]);
                ctx.globalAlpha = 1;
                ctx.fillStyle = pos.color;
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('▸', startX, chartArea.bottom + 12);

                // Small arrow at the right edge to indicate "continues"
                ctx.globalAlpha = 0.7;
                ctx.fillText('→', chartArea.right - 8, chartArea.bottom + 12);
            }
        });

        ctx.restore();
    }
};

// Helper function to convert hex color to rgba
function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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

// Store current tag positions for updates
let currentTagPositions = [];

async function initChart() {
    const result = await fetchData();
    const data = result.data;
    const stats = calculateStats(data);
    const yAxis = calculateAdaptiveYAxis(data);

    updateTitle(result.playerName, data.length);
    updateStatsDisplay(stats, data.length);
    renderTagLegend(result.tags);

    // Calculate tag positions for vertical lines
    currentTagPositions = findTagPositions(data, result.tags);

    const ctx = document.getElementById('mmrChart').getContext('2d');

    const gameLabels = data.map((_, index) => index + 1);

    // Register the plugin
    Chart.register(tagLinesPlugin);

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
                tagLines: {
                    tagPositions: currentTagPositions
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
    renderTagLegend(result.tags);

    // Update tag positions for vertical lines
    currentTagPositions = findTagPositions(data, result.tags);
    chart.options.plugins.tagLines.tagPositions = currentTagPositions;

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
