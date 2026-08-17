/**
 * XYPHER X // NEON CYBERPUNK CONTROL MATRIX JAVASCRIPT
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- STATE ---
  const state = {
    connectedBots: 4,
    voiceLocked: true,
    targetVcId: '1481261314981494877',
    volume: 150,
    looping: true,
    currentTrack: 'DISTRIBUTED (4 TRACKS)',
    spamming: false,
    whitelistedUsers: [
      { id: '1480822622429253643', role: 'PRIMARY COMMANDER' },
      { id: '1477645037004259379', role: 'SECONDARY COMMANDER' }
    ]
  };

  // --- AUDIO VISUALIZER SETUP ---
  const canvas = document.getElementById('audio-visualizer');
  const ctx = canvas.getContext('2d');
  let animationId = null;
  const numBars = 32;
  const barHeights = new Array(numBars).fill(10);

  function resizeCanvas() {
    canvas.width = canvas.parentElement.clientWidth - 32;
    canvas.height = 70;
  }
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  function drawVisualizer() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const barWidth = (canvas.width / numBars) - 3;

    for (let i = 0; i < numBars; i++) {
      // Simulate frequency fluctuation
      if (state.voiceLocked) {
        barHeights[i] += (Math.random() * 20 - 10);
        barHeights[i] = Math.max(8, Math.min(canvas.height - 8, barHeights[i]));
      } else {
        barHeights[i] = 4;
      }

      const x = i * (barWidth + 3);
      const height = barHeights[i];
      const y = canvas.height - height;

      // Neon Gradient
      const grad = ctx.createLinearGradient(0, canvas.height, 0, 0);
      grad.addColorStop(0, '#00f0ff');
      grad.addColorStop(0.5, '#9d4edd');
      grad.addColorStop(1, '#ff0055');

      ctx.fillStyle = grad;
      ctx.shadowBlur = 10;
      ctx.shadowColor = '#00f0ff';
      ctx.fillRect(x, y, barWidth, height);
      ctx.shadowBlur = 0;
    }

    animationId = requestAnimationFrame(drawVisualizer);
  }
  drawVisualizer();

  // --- GENERATE 21 TRACK PILLS ---
  const trackPillsContainer = document.getElementById('track-pills-list');
  for (let i = 1; i <= 21; i++) {
    const pill = document.createElement('button');
    pill.className = `track-pill-btn ${i === 1 ? 'active' : ''}`;
    pill.dataset.track = i;
    pill.textContent = `!${i}`;
    pill.title = `Play ${i}.mp3 on all bots`;
    pill.addEventListener('click', () => {
      document.querySelectorAll('.track-pill-btn').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      playTrack(i);
    });
    trackPillsContainer.appendChild(pill);
  }

  // --- LOG TERMINAL HELPER ---
  const terminalScreen = document.getElementById('terminal-screen');
  function logTerminal(msg, type = 'info') {
    const time = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `term-line ${type}`;
    line.textContent = `[${time}] ${msg}`;
    terminalScreen.appendChild(line);
    terminalScreen.scrollTop = terminalScreen.scrollHeight;
  }

  // --- TOAST NOTIFICATIONS ---
  const toastContainer = document.getElementById('toast-container');
  function showToast(text, icon = '⚡') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span>${icon}</span><span>${text}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 2800);
  }

  // --- COPY TO CLIPBOARD ---
  function copyText(text, label = 'Command') {
    navigator.clipboard.writeText(text).then(() => {
      showToast(`Copied ${label}: ${text}`, '📋');
      logTerminal(`Copied to clipboard: ${text}`, 'info');
    });
  }

  // --- ACTION HANDLERS ---

  // Lock VC Button
  const btnLockVc = document.getElementById('btn-lock-vc');
  const vcInput = document.getElementById('vc-id-input');
  btnLockVc.addEventListener('click', () => {
    const vcId = vcInput.value.trim() || '1481261314981494877';
    state.targetVcId = vcId;
    state.voiceLocked = true;
    document.getElementById('vc-status-pill').textContent = `LOCKED: ${vcId.slice(-6)}`;
    logTerminal(`[VOICE CORE]: Locking all 4 bots to VC ID: ${vcId}`, 'success');
    logTerminal(`[DISCORD CMD]: Execute "!ja ${vcId}" in Discord`, 'warning');
    copyText(`!ja ${vcId}`, 'Discord Voice Lock Command');
  });

  // Distributed Play Button (!p)
  const btnDistributed = document.getElementById('btn-distributed-play');
  btnDistributed.addEventListener('click', () => {
    state.currentTrack = 'DISTRIBUTED 4-TRACK MULTIPLEX';
    document.getElementById('now-playing-label').innerHTML = `CURRENT STREAM: <b>DISTRIBUTED 4-TRACK MULTIPLEX</b>`;
    logTerminal(`[PLAYBACK]: Multi-track distributed mode initiated (Track 1→Bot 0, Track 2→Bot 1...)`, 'success');
    copyText('!p', 'Distributed Playback Command');
  });

  // Play Specific Track
  function playTrack(trackNum) {
    state.currentTrack = `${trackNum}.mp3`;
    document.getElementById('now-playing-label').innerHTML = `CURRENT STREAM: <b>${trackNum}.mp3 (ALL BOTS)</b>`;
    logTerminal(`[PLAYBACK]: Track ${trackNum}.mp3 started across all bots with Infinite Loop`, 'info');
    copyText(`!${trackNum}`, `Play Track !${trackNum}`);
  }

  // Stop Audio Button
  const btnStopAudio = document.getElementById('btn-stop-audio');
  btnStopAudio.addEventListener('click', () => {
    logTerminal(`[PLAYBACK]: Audio playback stopped across all bots. (Bots remain in VC)`, 'warning');
    copyText('!s', 'Stop Audio Command');
  });

  // Disconnect VC Button
  const btnDisconnect = document.getElementById('btn-disconnect-vc');
  btnDisconnect.addEventListener('click', () => {
    state.voiceLocked = false;
    document.getElementById('vc-status-pill').textContent = 'VOICE: DISCONNECTED';
    logTerminal(`[VOICE CORE]: Disconnecting all bots from voice channels...`, 'danger');
    copyText('!dc', 'Disconnect Command');
  });

  // Volume Slider
  const volSlider = document.getElementById('volume-slider');
  const volDisplay = document.getElementById('volume-display');
  const statVolDisplay = document.getElementById('stat-vol-val');
  volSlider.addEventListener('input', (e) => {
    const val = e.target.value;
    state.volume = val;
    volDisplay.textContent = `${val}%`;
    statVolDisplay.textContent = `${val}%`;
    document.querySelector('.slider-header .cmd-code').textContent = `!vol ${val}`;
  });
  volSlider.addEventListener('change', (e) => {
    logTerminal(`[STATE SYNC]: Master volume set to ${e.target.value}%`, 'info');
    copyText(`!vol ${e.target.value}`, 'Volume Command');
  });

  // Loop Toggle
  const loopToggle = document.getElementById('loop-toggle');
  loopToggle.addEventListener('change', (e) => {
    state.looping = e.target.checked;
    logTerminal(`[STATE SYNC]: Audio Looping is now ${state.looping ? 'ENABLED (Infinite)' : 'DISABLED'}`, 'info');
    copyText('!loop', 'Loop Toggle Command');
  });

  // --- SPAM CANNON LOGIC ---
  const spamTextInput = document.getElementById('spam-text-input');
  const spamPreview = document.getElementById('spam-preview-text');
  let selectedCount = '100';

  spamTextInput.addEventListener('input', () => {
    let raw = spamTextInput.value.trim() || 'XYPHER X ALWAYS ON TOP BABE';
    if (!raw.startsWith('#')) raw = `# ${raw}`;
    spamPreview.textContent = raw;
  });

  document.querySelectorAll('.count-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.count-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedCount = btn.dataset.count;
    });
  });

  const btnFireSpam = document.getElementById('btn-fire-spam');
  const spamProgressBar = document.getElementById('spam-progress-bar');
  btnFireSpam.addEventListener('click', () => {
    const rawMsg = spamTextInput.value.trim() || 'XYPHER X ALWAYS ON TOP BABE';
    let cmd = `!spam`;
    if (selectedCount !== '30s') {
      cmd = `!spam ${selectedCount} ${rawMsg}`;
    } else {
      cmd = `!spam ${rawMsg}`;
    }

    btnFireSpam.classList.add('firing');
    spamProgressBar.style.width = '100%';
    logTerminal(`[SPAM CANNON]: ⚡ 100x ZERO-DELAY SPAM STORM FIRED: "${rawMsg}" (${selectedCount})`, 'danger');
    copyText(cmd, 'Spam Storm Command');

    setTimeout(() => {
      btnFireSpam.classList.remove('firing');
      spamProgressBar.style.width = '0%';
    }, 2500);
  });

  // --- WHITELIST CONTROLS ---
  const wlContainer = document.getElementById('whitelist-items-container');
  const addWlInput = document.getElementById('add-wl-input');
  const btnAddWl = document.getElementById('btn-add-wl');

  function renderWhitelist() {
    wlContainer.innerHTML = '';
    state.whitelistedUsers.forEach((u, idx) => {
      const row = document.createElement('div');
      row.className = 'whitelist-row';
      row.innerHTML = `
        <div class="wl-avatar">${idx === 0 ? '👑' : '⚡'}</div>
        <div class="wl-info">
          <div class="wl-id">${u.id}</div>
          <div class="wl-role">${u.role}</div>
        </div>
        <button class="btn-copy-sm" data-copy="${u.id}">COPY</button>
      `;
      row.querySelector('.btn-copy-sm').addEventListener('click', () => {
        copyText(u.id, 'User ID');
      });
      wlContainer.appendChild(row);
    });
    document.getElementById('whitelist-badge').textContent = `${state.whitelistedUsers.length} USERS`;
    document.getElementById('stat-whitelist-count').textContent = `${state.whitelistedUsers.length} ACTIVE`;
  }

  btnAddWl.addEventListener('click', () => {
    const newId = addWlInput.value.trim();
    if (!newId || !/^\d+$/.test(newId)) {
      showToast('Please enter a valid numeric Discord User ID', '⚠️');
      return;
    }
    state.whitelistedUsers.push({ id: newId, role: 'COMMANDER' });
    renderWhitelist();
    addWlInput.value = '';
    logTerminal(`[WHITELIST]: Added User ID ${newId} to whitelist`, 'success');
    copyText(`!u ${newId}`, 'Add Whitelist Command');
  });

  renderWhitelist();

  // Clear Terminal Button
  document.getElementById('btn-clear-console').addEventListener('click', () => {
    terminalScreen.innerHTML = '';
    logTerminal('[SYSTEM]: Terminal log cleared.', 'info');
  });

  // Copy Prefix Button
  document.getElementById('copy-bot-prefix-btn').addEventListener('click', () => {
    copyText('!', 'Bot Command Prefix');
  });

  // Command chips click-to-copy
  document.querySelectorAll('.cmd-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      copyText(chip.dataset.cmd, 'Command');
    });
  });
});
