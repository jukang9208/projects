// API 기본 설정
const API_BASE_URL = "";

//  DOM 요소 및 차트 초기화
const tabButtons = document.querySelectorAll('.tab-btn');
const singleForm = document.getElementById('single-form');
const compareForm = document.getElementById('compare-form');
const singleDashboard = document.getElementById('single-dashboard');
const compareDashboard = document.getElementById('compare-dashboard');
const chartCaption = document.getElementById('chartCaption');

// 단일 차트 placeholder / canvas
const chartPlaceholder = document.getElementById('chartPlaceholder');
const radarCanvas = document.getElementById('radarChart');

// 단일 기업용 레이더 차트
const ctx = radarCanvas;
let radarChart = new Chart(ctx, {
  type: 'radar',
  data: {
    labels: ['가치성', '안정성', '성장성', '수익성'],
    datasets: [{
      label: '분석 대기',
      data: [0, 0, 0, 0],
      fill: true,
      backgroundColor: 'rgba(37, 99, 235, 0.2)',
      borderColor: 'rgba(37, 99, 235, 1)',
      borderWidth: 2,
      pointRadius: 3
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'top' } },
    scales: {
      r: {
        min: 0,
        max: 100,
        ticks: { stepSize: 20, backdropColor: 'transparent' }
      }
    }
  }
});

// 비교 기업용 레이더 차트
const compCtx = document.getElementById('compareRadarChart');
let compareRadarChart = new Chart(compCtx, {
  type: 'radar',
  data: {
    labels: ['가치성', '안정성', '성장성', '수익성'],
    datasets: [
      {
        label: '기업A',
        data: [0, 0, 0, 0],
        fill: true,
        backgroundColor: 'rgba(37, 99, 235, 0.2)',
        borderColor: 'rgba(37, 99, 235, 1)',
        borderWidth: 2
      },
      {
        label: '기업B',
        data: [0, 0, 0, 0],
        fill: true,
        backgroundColor: 'rgba(16, 185, 129, 0.2)',
        borderColor: 'rgba(16, 185, 129, 1)',
        borderWidth: 2
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'top' } },
    scales: {
      r: {
        min: 0,
        max: 100,
        ticks: { stepSize: 20, backdropColor: 'transparent' }
      }
    }
  }
});

// 차트 표시 상태 제어
function showSingleChart() {
  if (chartPlaceholder) chartPlaceholder.style.display = 'none';
  if (radarCanvas) radarCanvas.style.display = 'block';
}

function hideSingleChart() {
  if (chartPlaceholder) chartPlaceholder.style.display = 'block';
  if (radarCanvas) radarCanvas.style.display = 'none';
}

// 초기 상태
hideSingleChart();

// UI 렌더링 헬퍼 함수
function getBadgeClass(value, type) {
  if (type === 'risk') {
    if (value <= 35) return ['positive', '낮은 리스크'];
    if (value <= 60) return ['neutral', '중립 리스크'];
    return ['negative', '높은 리스크'];
  }
  if (value >= 75) return ['positive', '긍정 우세'];
  if (value >= 45) return ['neutral', '중립 구간'];
  return ['negative', '보수 접근'];
}

function setBadge(el, value, type) {
  if (!el) return;
  const [klass, text] = getBadgeClass(value, type);
  el.className = `badge ${klass}`;
  el.textContent = text;
}

function renderMetricRows(rows) {
  const tbody = document.getElementById('metricBody');
  if (!tbody) return;
  tbody.innerHTML = rows.map(row => `<tr><td>${row[0]}</td><td>${row[1]}</td><td>${row[2]}</td></tr>`).join('');
}

function renderMemoRows(rows) {
  const tbody = document.getElementById('memoBody');
  if (!tbody) return;
  tbody.innerHTML = rows.map(row => `<tr><td>${row[0]}</td><td>${row[1]}</td></tr>`).join('');
}

function renderKeywords(items) {
  let wrap = document.getElementById('keywordList');
  if (!wrap) {
    const fallbackContainer = document.querySelector('.evidence-card');
    if (!fallbackContainer) return;
    wrap = document.createElement('div');
    wrap.id = 'keywordList';
    wrap.className = 'keyword-list';
    wrap.style.marginBottom = '15px';
    fallbackContainer.insertBefore(wrap, document.getElementById('evidenceList'));
  }
  wrap.innerHTML = items.map(item => `<span class="keyword-chip">${item}</span>`).join('');
}

function updateSummary(name, value, risk, opinion, confidence) {
  if (document.getElementById('statName')) document.getElementById('statName').textContent = name;
  if (document.getElementById('statValue')) document.getElementById('statValue').textContent = value;
  if (document.getElementById('statRisk')) document.getElementById('statRisk').textContent = risk;
  if (document.getElementById('statOpinion')) document.getElementById('statOpinion').textContent = opinion;
  if (document.getElementById('statConfidence')) document.getElementById('statConfidence').textContent = `신뢰도 ${confidence}%`;

  setBadge(document.getElementById('valueBadge'), value, 'value');
  setBadge(document.getElementById('riskBadge'), risk, 'risk');
}

function renderEvidence(items) {
  const wrap = document.getElementById('evidenceList');
  if (!wrap) return;
  if (!items || items.length === 0) {
    wrap.innerHTML = '<span class="keyword-chip">근거 데이터가 없습니다.</span>';
    return;
  }
  wrap.innerHTML = items.map(item => {
    if (typeof item === 'string') {
      return `<div class="evidence-item"><p class="evidence-summary">${item}</p></div>`;
    }
    return `<article class="evidence-item">
              <div class="evidence-top">
                <div class="evidence-title">${item.title || '핵심 요약'}</div>
                <div class="evidence-date">${item.date || ''}</div>
              </div>
              <p class="evidence-summary">${item.summary || ''}</p>
            </article>`;
  }).join('');
}

// API 데이터 연동 (단일 / 비교)
function renderSingleFromAPI(data, keyword) {
  const companyName = data.company_name || "기업";
  const quant = data.quant_analysis || data.quant_score || {};
  const metrics = data.metrics || {};
  const llm = data.llm_report || {};

  const valueScore = Math.round(Math.min(100, (quant.value_score || 0) * 4));
  const profitScore = Math.round(Math.min(100, (quant.profit_score || 0) * 4));
  const growthScore = Math.round(Math.min(100, (quant.growth_score || 0) * 4));
  const riskScore = Math.round(Math.min(100, (quant.risk_score || 0) * 4));
  const stabilityScore = Math.round(Math.min(100, (quant.stability_score || (25 - (quant.risk_score || 0))) * 4));

  const confidence = data.confidence_score || 0;
  const totalScore = data.total_score || quant.total_score || 0;

  updateSummary(companyName, totalScore, riskScore, llm.추천_의견 || "보유", confidence);
  if (document.getElementById('reportBox')) {
    document.getElementById('reportBox').textContent = llm.최종_의견 || "리포트가 없습니다.";
  }
  if (chartCaption) chartCaption.textContent = `${companyName} · 단일 기업 4축 점수`;

  const summaryArr = quant.analysis_summary || [];
  const growthContext = summaryArr.find(t => t.includes("성장") || t.includes("전환") || t.includes("감소")) || "데이터 확인 중";

  renderMetricRows([
    ["현재가", metrics.current_price ? `${metrics.current_price.toLocaleString()}원` : "N/A", "FDR 실시간가"],
    ["PER", metrics.per ? metrics.per.toFixed(2) : "N/A", "이익 대비 주가"],
    ["PBR", metrics.pbr ? metrics.pbr.toFixed(2) : "N/A", "자산 대비 주가"],
    ["ROE", metrics.roe ? `${metrics.roe.toFixed(1)}%` : "N/A", "수익성 지표"],
    ["성장성", growthContext, "전년비 실적"]
  ]);

  const shortIssues = Array.isArray(llm.핵심_요약) ? llm.핵심_요약 : [];
  renderMemoRows([
    ["시장 이슈", shortIssues[0] || "최근 동향 반영 [뉴스]"],
    ["재무 리스크", summaryArr.find(t => t.includes("PBR") || t.includes("리스크")) || "건전성 점검 [정량]"],
    ["데이터 검수", `신뢰도 ${confidence}% 기준 시스템 검증 완료`]
  ]);

  renderKeywords([keyword, companyName, "단일분석"].filter(Boolean));

  let newsTags = llm.뉴스_태그 || [];
  if (newsTags.length === 0 && shortIssues.length > 0) {
    newsTags.push({ title: `${companyName} 핵심 이슈`, summary: shortIssues.join(' / ') });
  }
  renderEvidence(newsTags.slice(0, 5));

  radarChart.data.datasets[0].label = companyName;
  radarChart.data.datasets[0].data = [valueScore, stabilityScore, growthScore, profitScore];
  radarChart.update();

  // 분석 후 placeholder 숨기고 차트 표시
  showSingleChart();
}

function renderCompareFromAPI(data, companyA, companyB, keyword) {
  const left = data.company_a || data.left || {};
  const right = data.company_b || data.right || {};

  const quantA = left.quant_analysis || left.quant_score || {};
  const quantB = right.quant_analysis || right.quant_score || {};
  const metricsA = left.metrics || {};
  const metricsB = right.metrics || {};
  const llmLeft = left.llm_report || {};
  const llmRight = right.llm_report || {};

  const totalA = left.total_score || quantA.total_score || 0;
  const totalB = right.total_score || quantB.total_score || 0;

  const valA = Math.round(Math.min(100, (quantA.value_score || 0) * 4));
  const valB = Math.round(Math.min(100, (quantB.value_score || 0) * 4));
  const riskA = Math.round(Math.min(100, (quantA.risk_score || 0) * 4));
  const riskB = Math.round(Math.min(100, (quantB.risk_score || 0) * 4));
  const stabA = Math.round(Math.min(100, (quantA.stability_score || (25 - (quantA.risk_score || 0))) * 4));
  const stabB = Math.round(Math.min(100, (quantB.stability_score || (25 - (quantB.risk_score || 0))) * 4));
  const growthA = Math.round(Math.min(100, (quantA.growth_score || 0) * 4));
  const growthB = Math.round(Math.min(100, (quantB.growth_score || 0) * 4));
  const profitA = Math.round(Math.min(100, (quantA.profit_score || 0) * 4));
  const profitB = Math.round(Math.min(100, (quantB.profit_score || 0) * 4));

  document.getElementById('thCompA').textContent = companyA;
  document.getElementById('thCompB').textContent = companyB;
  document.getElementById('thScoreA').textContent = companyA;
  document.getElementById('thScoreB').textContent = companyB;

  const tbodyMetric = document.getElementById('compareMetricBody');
  if (tbodyMetric) {
    tbodyMetric.innerHTML = `
      <tr>
        <td>현재가</td>
        <td style="color:#2563eb; font-weight:bold;">${metricsA.current_price ? metricsA.current_price.toLocaleString() + '원' : 'N/A'}</td>
        <td style="color:#10b981; font-weight:bold;">${metricsB.current_price ? metricsB.current_price.toLocaleString() + '원' : 'N/A'}</td>
        <td>최근 종가 기준</td>
      </tr>
      <tr>
        <td>PER</td>
        <td>${metricsA.per ? metricsA.per.toFixed(2) : 'N/A'}</td>
        <td>${metricsB.per ? metricsB.per.toFixed(2) : 'N/A'}</td>
        <td>낮을수록 이익 대비 저평가</td>
      </tr>
      <tr>
        <td>PBR</td>
        <td>${metricsA.pbr ? metricsA.pbr.toFixed(2) : 'N/A'}</td>
        <td>${metricsB.pbr ? metricsB.pbr.toFixed(2) : 'N/A'}</td>
        <td>낮을수록 자산 대비 저평가</td>
      </tr>
      <tr>
        <td>ROE</td>
        <td>${metricsA.roe ? metricsA.roe.toFixed(2) + '%' : 'N/A'}</td>
        <td>${metricsB.roe ? metricsB.roe.toFixed(2) + '%' : 'N/A'}</td>
        <td>높을수록 자본 대비 수익성 우수</td>
      </tr>
      <tr style="background-color: #f8fafc;">
        <td style="font-weight:bold;">종합 점수</td>
        <td style="font-size:18px; font-weight:bold; color:#2563eb;">${totalA}</td>
        <td style="font-size:18px; font-weight:bold; color:#10b981;">${totalB}</td>
        <td style="font-weight:bold;">${totalA > totalB ? companyA + ' 우위' : (totalA < totalB ? companyB + ' 우위' : '동점')}</td>
      </tr>
    `;
  }

  const tbodyScore = document.getElementById('compareScoreBody');
  if (tbodyScore) {
    tbodyScore.innerHTML = `
      <tr><td>가치성</td><td>${valA} / 100</td><td>${valB} / 100</td></tr>
      <tr><td>수익성</td><td>${profitA} / 100</td><td>${profitB} / 100</td></tr>
      <tr><td>안정성</td><td>${stabA} / 100</td><td>${stabB} / 100</td></tr>
      <tr><td>성장성</td><td>${growthA} / 100</td><td>${growthB} / 100</td></tr>
    `;
  }

  compareRadarChart.data.datasets[0].label = companyA;
  compareRadarChart.data.datasets[0].data = [valA, stabA, growthA, profitA];
  compareRadarChart.data.datasets[1].label = companyB;
  compareRadarChart.data.datasets[1].data = [valB, stabB, growthB, profitB];
  compareRadarChart.update();

  document.getElementById('compNameA').textContent = companyA;
  const opinionA = llmLeft.추천_의견 || '보유';
  const badgeA = document.getElementById('compOpinionA');
  badgeA.textContent = opinionA;
  badgeA.className = `badge ${opinionA.includes('매수') ? 'positive' : opinionA.includes('주의') || opinionA.includes('관망') ? 'negative' : 'neutral'}`;
  document.getElementById('compReportA').textContent = llmLeft.최종_의견 || '리포트가 없습니다.';
  document.getElementById('compMemoA').innerHTML = (quantA.analysis_summary || []).slice(0, 3).map(m => `<li>${m}</li>`).join('') || '<li>데이터 없음</li>';

  document.getElementById('compNameB').textContent = companyB;
  const opinionB = llmRight.추천_의견 || '보유';
  const badgeB = document.getElementById('compOpinionB');
  badgeB.textContent = opinionB;
  badgeB.className = `badge ${opinionB.includes('매수') ? 'positive' : opinionB.includes('주의') || opinionB.includes('관망') ? 'negative' : 'neutral'}`;
  document.getElementById('compReportB').textContent = llmRight.최종_의견 || '리포트가 없습니다.';
  document.getElementById('compMemoB').innerHTML = (quantB.analysis_summary || []).slice(0, 3).map(m => `<li>${m}</li>`).join('') || '<li>데이터 없음</li>';

  renderKeywords([keyword, companyA, companyB, "비교분석"].filter(Boolean));

  let newsA = llmLeft.뉴스_태그 || [];
  let newsB = llmRight.뉴스_태그 || [];
  let combinedNews = [...newsA.slice(0, 3), ...newsB.slice(0, 3)];

  if (combinedNews.length === 0) {
    let summaryA = Array.isArray(llmLeft.핵심_요약) ? llmLeft.핵심_요약.join(" / ") : llmLeft.핵심_요약;
    let summaryB = Array.isArray(llmRight.핵심_요약) ? llmRight.핵심_요약.join(" / ") : llmRight.핵심_요약;
    if (summaryA) combinedNews.push({ title: `[${companyA}] 핵심 이슈`, summary: summaryA });
    if (summaryB) combinedNews.push({ title: `[${companyB}] 핵심 이슈`, summary: summaryB });
  }

  renderEvidence(combinedNews.length > 0 ? combinedNews : ["뉴스 데이터가 없습니다."]);
}

// 초기화(리셋) 전용 함수
function resetSingleUI() {
  document.getElementById('singleTicker').value = '';
  document.getElementById('singleKeyword').value = '';
  document.getElementById('singleMode').selectedIndex = 0;

  updateSummary('-', '0', '0', '분석 전', '0');
  setBadge(document.getElementById('valueBadge'), 0, 'value');
  setBadge(document.getElementById('riskBadge'), 0, 'risk');
  document.getElementById('valueBadge').textContent = '대기중';
  document.getElementById('riskBadge').textContent = '대기중';

  if (document.getElementById('chartCaption')) {
    document.getElementById('chartCaption').textContent = '단일 기업 4축 점수';
  }
  if (document.getElementById('reportBox')) {
    document.getElementById('reportBox').textContent = '분석 버튼을 누르면 AI가 재무와 뉴스를 종합하여 리포트를 생성합니다.';
  }

  if (document.getElementById('metricBody')) document.getElementById('metricBody').innerHTML = '';
  if (document.getElementById('memoBody')) document.getElementById('memoBody').innerHTML = '';
  if (document.getElementById('keywordList')) document.getElementById('keywordList').innerHTML = '';
  if (document.getElementById('evidenceList')) document.getElementById('evidenceList').innerHTML = '';

  radarChart.data.datasets[0].label = '분석 대기';
  radarChart.data.datasets[0].data = [0, 0, 0, 0];
  radarChart.update();

  // 초기화 시 차트 숨기고 안내 문구 표시
  hideSingleChart();
}

function resetCompareUI() {
  document.getElementById('compareTickerA').value = '';
  document.getElementById('compareTickerB').value = '';
  document.getElementById('compareKeyword').value = '';
  document.getElementById('compareFocus').selectedIndex = 0;

  document.getElementById('thCompA').textContent = '기업A';
  document.getElementById('thCompB').textContent = '기업B';
  document.getElementById('thScoreA').textContent = '기업A';
  document.getElementById('thScoreB').textContent = '기업B';

  if (document.getElementById('compareMetricBody')) document.getElementById('compareMetricBody').innerHTML = '';
  if (document.getElementById('compareScoreBody')) document.getElementById('compareScoreBody').innerHTML = '';

  compareRadarChart.data.datasets[0].label = '기업A';
  compareRadarChart.data.datasets[0].data = [0, 0, 0, 0];
  compareRadarChart.data.datasets[1].label = '기업B';
  compareRadarChart.data.datasets[1].data = [0, 0, 0, 0];
  compareRadarChart.update();

  document.getElementById('compNameA').textContent = '기업A';
  document.getElementById('compOpinionA').textContent = '의견 대기';
  document.getElementById('compOpinionA').className = 'badge neutral';
  document.getElementById('compReportA').textContent = '분석 대기 중...';
  document.getElementById('compMemoA').innerHTML = '<li>분석을 실행해주세요.</li>';

  document.getElementById('compNameB').textContent = '기업B';
  document.getElementById('compOpinionB').textContent = '의견 대기';
  document.getElementById('compOpinionB').className = 'badge neutral';
  document.getElementById('compReportB').textContent = '분석 대기 중...';
  document.getElementById('compMemoB').innerHTML = '<li>분석을 실행해주세요.</li>';

  if (document.getElementById('keywordList')) document.getElementById('keywordList').innerHTML = '';
  if (document.getElementById('evidenceList')) document.getElementById('evidenceList').innerHTML = '';
}

// 탭 전환 및 이벤트 리스너 로직
tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tabButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const mode = btn.dataset.tab;
    if (singleForm) singleForm.classList.toggle('active', mode === 'single');
    if (compareForm) compareForm.classList.toggle('active', mode === 'compare');

    if (singleDashboard) singleDashboard.style.display = mode === 'single' ? 'block' : 'none';
    if (compareDashboard) compareDashboard.style.display = mode === 'compare' ? 'block' : 'none';
  });
});

if (document.getElementById('runSingle')) {
  document.getElementById('runSingle').addEventListener('click', async () => {
    const company = document.getElementById('singleTicker').value.trim() || '삼성전자';
    const keyword = document.getElementById('singleKeyword').value.trim() || '';
    const mode = document.getElementById('singleMode').value || '종합 분석';

    const btn = document.getElementById('runSingle');
    btn.textContent = "분석 중...";
    btn.disabled = true;

    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: company,
          focus_keyword: keyword,
          analysis_mode: mode,
          force_refresh: false
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(`(${response.status}) ${errData.detail || '요청 실패'}`);
      }

      const data = await response.json();
      renderSingleFromAPI(data, keyword);
    } catch (error) {
      console.error(error);
      alert("단일 기업 분석 중 오류가 발생했습니다.\n" + error.message);
      hideSingleChart();
    } finally {
      btn.textContent = "기업 분석 실행";
      btn.disabled = false;
    }
  });
}

if (document.getElementById('runCompare')) {
  document.getElementById('runCompare').addEventListener('click', async () => {
    const a = document.getElementById('compareTickerA').value.trim() || '삼성전자';
    const b = document.getElementById('compareTickerB').value.trim() || 'SK하이닉스';
    const keyword = document.getElementById('compareKeyword').value.trim() || '';
    const focus = document.getElementById('compareFocus').value || '종합 평가 비교';

    const btn = document.getElementById('runCompare');
    btn.textContent = "비교 중...";
    btn.disabled = true;

    try {
      const response = await fetch(`${API_BASE_URL}/api/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_a: a,
          company_b: b,
          focus_keyword: keyword,
          compare_focus: focus,
          force_refresh: false
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(`(${response.status}) ${errData.detail || '요청 실패'}`);
      }

      const data = await response.json();
      renderCompareFromAPI(data, a, b, keyword);
    } catch (error) {
      console.error(error);
      alert("비교 분석 중 오류가 발생했습니다.\n" + error.message);
    } finally {
      btn.textContent = "두 기업 비교 분석 실행";
      btn.disabled = false;
    }
  });
}

if (document.getElementById('resetSingle')) {
  document.getElementById('resetSingle').addEventListener('click', () => {
    resetSingleUI();
  });
}

if (document.getElementById('resetCompare')) {
  document.getElementById('resetCompare').addEventListener('click', () => {
    resetCompareUI();
  });
}