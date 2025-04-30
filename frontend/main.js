let chartDom = document.getElementById('map');
let myChart = echarts.init(chartDom);
let detailedData = {};
let lastClickedProvince = null;
let currentServer = null;
let isInfoCollapsed = false;
let isServerCollapsed = false;
const servers = [
  { name: "ClawCloud HK CN-Opt", ip: "https://clawcloud-hk-cnopt-tcpingmap.aunet.dpdns.org" },
  { name: "ClawCloud JP INTL", ip: "https://clawcloud-jp-intl-tcpingmap.aunet.dpdns.org" },
  { name: "Sharon HK Premium", ip: "https://hkg.pre.sharon.tcpingmap.aunet.dpdns.org" },
  { name: "Sharon SG Premium", ip: "https://sin.pre.sharon.tcpingmap.aunet.dpdns.org" },
  { name: "Sharon JP Premium", ip: "https://jpn.pre.sharon.tcpingmap.aunet.dpdns.org" },
  { name: "Sharon KR Premium", ip: "https://kor.pre.sharon.tcpingmap.aunet.dpdns.org" }
];

function updateLastUpdateTime() {
  const now = new Date();
  const timeString = now.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
  document.getElementById('update-time').textContent = timeString;
}

function toggleInfoPanel() {
  const infoBox = document.getElementById('info-box');
  const content = document.getElementById('info-content');
  const button = document.querySelector('#info-box .toggle-icon');
  isInfoCollapsed = !isInfoCollapsed;
  if (isInfoCollapsed) {
    infoBox.classList.add('collapsed');
    content.classList.add('collapsed');
    button.textContent = '▼';
  } else {
    infoBox.classList.remove('collapsed');
    content.classList.remove('collapsed');
    button.textContent = '▲';
  }
}

function toggleServerSelector() {
  const selector = document.getElementById('server-selector');
  const toggleButton = document.getElementById('toggle-server-button');
  isServerCollapsed = true;
  selector.classList.add('collapsed');
  toggleButton.classList.add('visible');
}

function showServerSelector() {
  const selector = document.getElementById('server-selector');
  const toggleButton = document.getElementById('toggle-server-button');
  isServerCollapsed = false;
  selector.classList.remove('collapsed');
  toggleButton.classList.remove('visible');
}

function renderServerList() {
  const serverList = document.getElementById('server-list');
  serverList.innerHTML = servers.map(server => `
    <button
      class="server-item ${currentServer === server.ip ? 'selected' : ''}"
      onclick="switchServer('${server.ip}')"
    >
      ${server.name}
    </button>
  `).join('');
}

function switchServer(ip) {
  currentServer = ip;
  renderServerList();
  fetchData();
}

function getLatencyClass(latency) {
  if (latency < 100) return 'latency-good';
  if (latency < 200) return 'latency-medium';
  return 'latency-high';
}

async function fetchData() {
  if (!currentServer) return;

  const loading = document.getElementById('loading');
  const loadingContent = document.querySelector('.loading-content');
  const timeoutDuration = 10000; // 10秒超时

  loading.style.display = 'flex';
  loadingContent.innerHTML = `
    <div class="loading-spinner"></div>
    <span>加载中...</span>
  `;

  try {
    // 创建超时 Promise
    const timeout = new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error('加载超时'));
      }, timeoutDuration);
    });

    // 竞争 fetch 和 timeout
    const response = await Promise.race([
      fetch(`${currentServer}/get_results`),
      timeout
    ]);

    if (!response.ok) throw new Error(`HTTP 错误: ${response.status}`);

    const data = await response.json();
    const provinceData = {};
    detailedData = {};

    for (const key in data) {
      const [province, cityOperator] = key.split("-");
      const { average_delay } = data[key];
      if (!provinceData[province]) {
        provinceData[province] = { totalDelay: 0, totalCount: 0 };
      }
      provinceData[province].totalDelay += average_delay || 0;
      provinceData[province].totalCount += 1;
      if (!detailedData[province]) {
        detailedData[province] = [];
      }
      detailedData[province].push({
        name: cityOperator,
        average_delay
      });
    }

    const mapData = Object.keys(provinceData).map(province => ({
      name: province,
      value: (provinceData[province].totalDelay / provinceData[province].totalCount) || null
    }));

    updateChart(mapData);
    updateInfoPanel();
    updateLastUpdateTime();

  } catch (error) {
    console.error('Error fetching data:', error);

    // 显示超时提示
    loadingContent.innerHTML = `
      <span style="color: #dc2626;">加载超时，请稍后重试</span>
    `;

  } finally {
    // 2秒后隐藏加载动画
    setTimeout(() => {
      loading.style.display = 'none';
    }, 2000);
  }
}

function updateChart(mapData) {
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: function (params) {
        const province = params.name;
        return `<strong>${province}</strong><br>平均延迟: ${params.value ? `${params.value.toFixed(2)} ms` : '暂无数据'}`;
      }
    },
    visualMap: {
      min: 0,
      max: 300,
      left: 'left',
      bottom: 30,
      text: ['高延迟', '低延迟'],
      calculable: true,
      inRange: {
        color: ['#31c27c', '#ffeb3b', '#f44336']
      },
      textStyle: {
        color: '#333'
      }
    },
    series: [{
      name: 'Ping延迟',
      type: 'map',
      map: 'china',
      roam: true,
      emphasis: {
        label: {
          show: true,
          color: '#333'
        },
        itemStyle: {
          areaColor: '#b8e0f6'
        }
      },
      label: {
        show: true,
        color: '#333',
        fontSize: 10
      },
      itemStyle: {
        areaColor: '#e0e8f0',
        borderColor: '#ccc'
      },
      data: mapData
    }]
  };
  myChart.setOption(option);
  myChart.off('click');
  myChart.on('click', function(params) {
    handleProvinceClick(params.name);
  });
}

function handleProvinceClick(province) {
  if (province === lastClickedProvince) {
    lastClickedProvince = null;
    document.getElementById('info-title').innerText = '全国详细信息';
  } else if (detailedData[province]) {
    lastClickedProvince = province;
    document.getElementById('info-title').innerText = `${province}详细信息`;
    if (isInfoCollapsed) {
      toggleInfoPanel();
    }
  } else {
    lastClickedProvince = null;
    document.getElementById('info-title').innerText = '全国详细信息';
  }
  updateInfoPanel();
}

function updateInfoPanel() {
  const content = document.getElementById('info-content');
  if (lastClickedProvince && detailedData[lastClickedProvince]) {
    content.innerHTML = detailedData[lastClickedProvince].map(item => `
      <div style="background: white; padding: 0.5rem; margin-bottom: 0.5rem; border-radius: 0.375rem; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);">
        <div style="font-weight: 500; color: #1f2937;">${item.name}</div>
        <div style="font-size: 0.875rem; color: #6b7280;">
          平均延迟: <span class="${getLatencyClass(item.average_delay)}">${item.average_delay} ms</span>
        </div>
      </div>
    `).join('');
  } else {
    content.innerHTML = Object.keys(detailedData).map(province => `
      <div style="margin-bottom: 1rem;">
        <h4 style="font-weight: 500; color: #1f2937; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.25rem; margin-bottom: 0.5rem;">
          ${province}
        </h4>
        <div style="margin-left: 0.5rem;">
          ${detailedData[province].map(item => `
            <div style="display: flex; justify-content: space-between; font-size: 0.875rem; margin-bottom: 0.25rem;">
              <span style="color: #4b5563;">${item.name}:</span>
              <span class="${getLatencyClass(item.average_delay)}">${item.average_delay} ms</span>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  }
}

window.addEventListener('resize', function() {
  myChart.resize();
});

// 初始化
window.onload = function() {
  if (servers.length > 0) {
    currentServer = servers[0].ip;
    renderServerList();
    fetchData();
    setInterval(fetchData, 90000); // 每 90 秒自动刷新
  }
};