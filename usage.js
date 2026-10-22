'use strict';

window.NanCyUsage = (() => {
  const fields = ['lifetimeTokens', 'peakDailyTokens', 'currentStreakDays', 'longestStreakDays', 'longestRunningTurnSec'];
  const number = new Intl.NumberFormat('zh-CN');
  let savedSnapshot = null;
  let activeController = null;
  let requestNumber = 0;

  function checkedNumber(value) {
    if (value === null || value === undefined) return null;
    if (!Number.isSafeInteger(value) || value < 0) throw new Error('invalid-statistics');
    return value;
  }

  function validate(data) {
    if (!data || data.schemaVersion !== 1 || !data.summary || !Number.isFinite(Date.parse(data.updatedAt))) {
      throw new Error('invalid-snapshot');
    }
    const summary = Object.fromEntries(fields.map(key => [key, checkedNumber(data.summary[key])]));
    let days = null;
    if (data.dailyUsageBuckets !== null) {
      if (!Array.isArray(data.dailyUsageBuckets)) throw new Error('invalid-days');
      days = data.dailyUsageBuckets.map(day => {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(day.startDate) || !Number.isFinite(Date.parse(day.startDate))) {
          throw new Error('invalid-date');
        }
        const tokens = checkedNumber(day.tokens);
        if (tokens === null) throw new Error('missing-tokens');
        return { startDate: day.startDate, tokens };
      }).sort((a, b) => a.startDate.localeCompare(b.startDate));
    }
    return { updatedAt: data.updatedAt, summary, days };
  }

  function cancel() {
    requestNumber += 1;
    if (activeController) activeController.abort();
    activeController = null;
  }

  function timeLabel(value) {
    return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai' }).format(new Date(value));
  }

  function paint(main, data) {
    fields.forEach(key => {
      const element = main.querySelector(`[data-usage="${key}"]`);
      const value = data.summary[key];
      if (key === 'longestRunningTurnSec') {
        element.textContent = value === null ? '暂未提供' : `${number.format(Math.floor(value / 3600))} 小时 ${Math.floor(value % 3600 / 60)} 分钟`;
      } else {
        element.textContent = value === null ? '暂未提供' : number.format(value);
      }
    });
    main.querySelector('.usage-updated time').textContent = timeLabel(data.updatedAt);
    main.querySelector('.usage-updated time').dateTime = data.updatedAt;
    main.querySelector('.usage-age').textContent = Date.now() - Date.parse(data.updatedAt) > 2 * 60 * 60 * 1000
      ? '这份统计已超过 2 小时未更新，请留意同步时间。' : '';
    const chart = main.querySelector('.usage-activity');
    const tableBody = main.querySelector('.usage-table tbody');
    chart.replaceChildren();
    tableBody.replaceChildren();
    const days = data.days && data.days.slice(-60);
    const details = main.querySelector('.usage-days');
    details.hidden = !days || !days.length;
    if (!days || !days.length) {
      const empty = document.createElement('p');
      empty.className = 'usage-muted';
      empty.textContent = '官方暂未返回每日活动数据。';
      chart.append(empty);
      main.querySelector('.usage-range').textContent = '';
      return;
    }
    const max = Math.max(1, ...days.map(day => day.tokens));
    const bars = document.createElement('div');
    bars.className = 'usage-bars';
    bars.setAttribute('role', 'img');
    bars.setAttribute('aria-label', `最近 ${days.length} 个有记录日期的 Token 活动。下方可展开完整数据表。`);
    days.forEach(day => {
      const bar = document.createElement('div');
      bar.className = 'usage-bar';
      bar.style.height = `${Math.max(day.tokens ? 1 : 0, day.tokens / max * 100)}%`;
      bar.title = `${day.startDate}：${number.format(day.tokens)} Token`;
      bars.append(bar);
      const row = document.createElement('tr');
      const date = document.createElement('td');
      date.textContent = day.startDate;
      const value = document.createElement('td');
      value.textContent = number.format(day.tokens);
      row.append(date, value);
      tableBody.prepend(row);
    });
    chart.append(bars);
    main.querySelector('.usage-range').textContent = `${days[0].startDate} — ${days[days.length - 1].startDate} · ${days.length} 个有记录日期`;
  }

  async function refresh() {
    const main = document.querySelector('main');
    if (!main.querySelector('.usage-page') || activeController) return;
    const controller = new AbortController();
    activeController = controller;
    const currentRequest = ++requestNumber;
    const button = main.querySelector('#usage-refresh');
    const status = main.querySelector('#usage-status');
    button.disabled = true;
    button.textContent = '正在获取…';
    status.textContent = '正在读取最近一次同步的统计…';
    main.querySelector('.usage-page').setAttribute('aria-busy', 'true');
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const url = new URL('gpt-usage.json', document.baseURI);
      url.searchParams.set('t', String(Date.now()));
      const response = await fetch(url, { cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error('fetch-failed');
      const snapshot = validate(await response.json());
      if (currentRequest !== requestNumber || !main.querySelector('.usage-page')) return;
      savedSnapshot = snapshot;
      paint(main, snapshot);
      status.textContent = '已读取最近一次同步结果。';
    } catch (error) {
      if (currentRequest !== requestNumber || !main.querySelector('.usage-page')) return;
      if (savedSnapshot) paint(main, savedSnapshot);
      status.textContent = savedSnapshot
        ? '这次刷新未成功，以下保留上次获取的统计。请稍后重试。'
        : '暂时无法获取统计，请稍后重试，或查看官方页面。';
    } finally {
      clearTimeout(timeout);
      if (currentRequest === requestNumber) {
        activeController = null;
        if (main.querySelector('.usage-page')) {
          button.disabled = false;
          button.textContent = '刷新用量 ↻';
          main.querySelector('.usage-page').setAttribute('aria-busy', 'false');
        }
      }
    }
  }

  function render(main) {
    document.title = '我的 GPT 使用量 · NanCy';
    main.innerHTML = `<section class="usage-page" aria-busy="false">
      <div class="page-heading"><div class="eyebrow">MY GPT ACTIVITY</div><h1>我的 GPT 使用量</h1><p>把好奇写进问题，也把探索留成记录。</p></div>
      <div class="usage-toolbar"><div><p class="usage-updated">数据同步于 <time>—</time> <span>（北京时间）</span></p><p class="usage-muted">每次打开或点击刷新，读取最近一次同步结果。</p></div><button class="secondary" id="usage-refresh" type="button">刷新用量 ↻</button></div>
      <p id="usage-status" class="usage-status" role="status" aria-live="polite"></p><p class="usage-age" role="status"></p>
      <div class="usage-stats">
        <section class="usage-stat"><h2>累计 Token</h2><p data-usage="lifetimeTokens">—</p><small>官方累计用量</small></section>
        <section class="usage-stat"><h2>单日最高 Token</h2><p data-usage="peakDailyTokens">—</p><small>最投入的一天</small></section>
        <section class="usage-stat"><h2>当前连续使用</h2><p><span data-usage="currentStreakDays">—</span><small>天</small></p></section>
        <section class="usage-stat"><h2>最长连续使用</h2><p><span data-usage="longestStreakDays">—</span><small>天</small></p></section>
      </div>
      <section class="usage-history"><div class="section-head"><h2>Token 活动<small>DAILY ACTIVITY</small></h2></div><p class="usage-range usage-muted"></p><div class="usage-activity"><p class="usage-muted">等待统计数据…</p></div>
        <details class="usage-days" hidden><summary>查看每日数据</summary><div class="usage-table-wrap"><table class="usage-table"><thead><tr><th scope="col">日期</th><th scope="col">Token</th></tr></thead><tbody></tbody></table></div></details>
      </section>
      <div class="usage-footnote"><p>最长单次任务：<span data-usage="longestRunningTurnSec">—</span></p><p>这是用量活动统计，不代表剩余配额或费用；未返回的指标显示“暂未提供”。</p><a class="text-link" href="https://chatgpt.com/u/1724910470" target="_blank" rel="noopener noreferrer">查看我的官方页面 ↗</a></div>
    </section>`;
    main.querySelector('#usage-refresh').onclick = refresh;
    if (savedSnapshot) paint(main, savedSnapshot);
    refresh();
  }

  return { render, refresh, cancel };
})();
