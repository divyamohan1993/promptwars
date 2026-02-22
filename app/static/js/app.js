/**
 * QuestForge: The Upside Down
 * Frontend Application (Vanilla JS)
 *
 * Modules:
 *  1. API       — Server communication (fetch wrapper)
 *  2. Sound     — Web Audio API synthesised SFX
 *  3. MapRender — Canvas 2D procedural map
 *  4. Scene     — Visual scene-card rendering + icon lookup
 *  5. A11y      — Accessibility helpers (screen-reader announcements)
 *  6. Game      — Main controller (state, UI, Google service integration)
 *
 * Google Cloud services used from the frontend:
 *  - Gemini AI       (via /api/game/start, /api/game/action)
 *  - Cloud TTS       (via /api/game/tts)
 *  - Cloud Translate  (via /api/game/translate)
 *  - Vertex AI Imagen (via /api/game/image)
 */

"use strict";

/* ============================================================
   1. API Client
   ============================================================ */
const API = {
  async startGame(playerName, adventure, language) {
    const res = await fetch("/api/game/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_name: playerName, adventure, language }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }
    return res.json();
  },

  async sendAction(gameId, action) {
    const res = await fetch("/api/game/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ game_id: gameId, action }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }
    return res.json();
  },

  async getGameState(gameId) {
    const res = await fetch(`/api/game/${gameId}`);
    if (!res.ok) throw new Error(`Server error (${res.status})`);
    return res.json();
  },

  async narrateAudio(text) {
    const res = await fetch("/api/game/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.audio;
  },

  async translateText(text, targetLanguage) {
    const res = await fetch("/api/game/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, target_language: targetLanguage }),
    });
    if (!res.ok) return null;
    return res.json();
  },

  async generateImage(prompt) {
    const res = await fetch("/api/game/image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) return null;
    return res.json();
  },
};

/* ============================================================
   2. Sound Manager (Web Audio API)
   ============================================================ */
const Sound = {
  ctx: null,
  enabled: true,
  _initialized: false,

  init() {
    const handler = () => {
      if (!this._initialized) {
        try {
          this.ctx = new (window.AudioContext || window.webkitAudioContext)();
          this._initialized = true;
        } catch (_) { /* no audio support */ }
      }
    };
    document.addEventListener("click", handler, { once: true });
    document.addEventListener("keydown", handler, { once: true });
  },

  _tone(freq, dur, type, vol) {
    if (!this.ctx || !this.enabled) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = type || "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(vol || 0.12, this.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + dur);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start();
    osc.stop(this.ctx.currentTime + dur);
  },

  click()   { this._tone(800, 0.05, "square", 0.08); },
  item()    { this._tone(523, 0.1); setTimeout(() => this._tone(659, 0.1), 100); setTimeout(() => this._tone(784, 0.15), 200); },
  damage()  { this._tone(200, 0.15, "sawtooth", 0.1); },
  heal()    { this._tone(440, 0.1); setTimeout(() => this._tone(660, 0.15), 150); },
  achieve() { this._tone(659, 0.08); setTimeout(() => this._tone(784, 0.08), 80); setTimeout(() => this._tone(1047, 0.2), 160); },
  victory() { [523,659,784,1047].forEach((f,i) => setTimeout(() => this._tone(f, 0.2), i*120)); },
  defeat()  { [400,350,300,200].forEach((f,i) => setTimeout(() => this._tone(f, 0.2, "sawtooth", 0.08), i*150)); },
};

/* ============================================================
   3. Map Renderer (Canvas 2D)
   ============================================================ */
const MapRender = {
  canvas: null,
  ctx: null,

  init(canvasEl) {
    this.canvas = canvasEl;
    this.ctx = canvasEl.getContext("2d");
  },

  render(nodes, currentId) {
    if (!this.ctx) return;
    const c = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    c.clearRect(0, 0, w, h);
    c.fillStyle = "#0a0a0f";
    c.fillRect(0, 0, w, h);

    if (!nodes || nodes.length === 0) {
      c.fillStyle = "#333346";
      c.font = "11px system-ui";
      c.textAlign = "center";
      c.fillText("Explore to reveal the map!", w / 2, h / 2);
      return;
    }

    const padX = 35, padY = 30;
    const stepX = Math.min(55, (w - padX * 2) / Math.max(4, Math.max(...nodes.map(n => n.x)) + 1));
    const stepY = Math.min(45, (h - padY * 2) / Math.max(3, Math.max(...nodes.map(n => n.y)) + 1));

    const pos = (n) => ({ x: padX + n.x * stepX, y: padY + n.y * stepY });

    // Connections
    c.strokeStyle = "#333346";
    c.lineWidth = 2;
    nodes.forEach(node => {
      const from = pos(node);
      node.connected_to.forEach(tid => {
        const target = nodes.find(n => n.node_id === tid);
        if (target) {
          const to = pos(target);
          c.beginPath();
          c.moveTo(from.x, from.y);
          c.lineTo(to.x, to.y);
          c.stroke();
        }
      });
    });

    // Nodes
    nodes.forEach(node => {
      const p = pos(node);
      const isCurrent = node.node_id === currentId;
      const r = isCurrent ? 10 : 7;

      // Glow for current
      if (isCurrent) {
        c.save();
        c.shadowColor = "#cc2200";
        c.shadowBlur = 15;
        c.beginPath();
        c.arc(p.x, p.y, r + 3, 0, Math.PI * 2);
        c.fillStyle = "rgba(204,34,0,0.3)";
        c.fill();
        c.restore();
      }

      c.beginPath();
      c.arc(p.x, p.y, r, 0, Math.PI * 2);
      c.fillStyle = isCurrent ? "#cc2200" : (node.visited ? "#00d4ff" : "#333346");
      c.fill();
      c.strokeStyle = isCurrent ? "#ff4422" : "#555";
      c.lineWidth = 1;
      c.stroke();

      // Icon
      const icons = { forest: "\u{1F332}", lab: "\u{1F52C}", school: "\u{1F3EB}", house: "\u{1F3E0}", cave: "\u{1F573}", town: "\u{1F3D8}", library: "\u{1F4DA}", arcade: "\u{1F579}", field: "\u{1F33E}", portal: "\u{1F300}", "bike-trail": "\u{1F6B2}", basement: "\u{1F3E0}" };
      const icon = icons[node.icon] || "\u{1F4CD}";
      c.font = "10px system-ui";
      c.textAlign = "center";
      c.fillText(icon, p.x, p.y - r - 4);

      // Label
      c.fillStyle = "#e8e0d0";
      c.font = "9px system-ui";
      c.fillText(node.name.length > 12 ? node.name.slice(0, 11) + "\u2026" : node.name, p.x, p.y + r + 12);
    });
  },
};

/* ============================================================
   4. Scene Renderer
   ============================================================ */
const Scene = {
  MOOD_ICONS: {
    mysterious: "\u{1F52E}", cheerful: "\u{2600}\u{FE0F}", tense: "\u26A1",
    scary: "\u{1F47B}", victorious: "\u{1F3C6}", calm: "\u{1F343}",
    exciting: "\u{1F525}", neutral: "\u{2728}",
  },
  LOCATION_ICONS: {
    forest: "\u{1F332}", lab: "\u{1F52C}", school: "\u{1F3EB}", house: "\u{1F3E0}",
    cave: "\u{1F573}\u{FE0F}", town: "\u{1F3D8}\u{FE0F}", library: "\u{1F4DA}", arcade: "\u{1F579}\u{FE0F}",
    field: "\u{1F33E}", portal: "\u{1F300}", "bike-trail": "\u{1F6B2}", basement: "\u{1F3E0}",
  },
  CHOICE_ICONS: {
    sword: "\u2694\u{FE0F}", shield: "\u{1F6E1}\u{FE0F}", "magnifying-glass": "\u{1F50D}",
    flashlight: "\u{1F526}", run: "\u{1F3C3}", talk: "\u{1F4AC}", key: "\u{1F511}",
    bike: "\u{1F6B2}", "walkie-talkie": "\u{1F4FB}", book: "\u{1F4D6}",
    potion: "\u{1F9EA}", friend: "\u{1F91D}", sneak: "\u{1F43E}", climb: "\u{1FA78}",
    door: "\u{1F6AA}", puzzle: "\u{1F9E9}", magic: "\u{1FA84}", hide: "\u{1F648}",
  },
  ITEM_ICONS: {
    flashlight: "\u{1F526}", "walkie-talkie": "\u{1F4FB}", bike: "\u{1F6B2}",
    key: "\u{1F511}", sword: "\u2694\u{FE0F}", shield: "\u{1F6E1}\u{FE0F}",
    map: "\u{1F5FA}\u{FE0F}", potion: "\u{1F9EA}", book: "\u{1F4D6}",
    torch: "\u{1F525}", compass: "\u{1F9ED}", rope: "\u{1FAA2}",
    gem: "\u{1F48E}", coin: "\u{1FA99}", ring: "\u{1F48D}",
    wand: "\u{1FA84}", helmet: "\u26D1\u{FE0F}", scroll: "\u{1F4DC}",
  },
  ACHIEVEMENT_ICONS: {
    "First Steps": "\u{1F463}", Explorer: "\u{1F5FA}\u{FE0F}", Collector: "\u{1F392}",
    Survivor: "\u{1F3C5}", "Brave Heart": "\u{1F9E1}", "Full Health": "\u{1F49A}",
  },

  renderSceneCard(visual, els) {
    if (!visual) return;
    // Background mood
    const bg = els.sceneBg;
    bg.className = "scene-bg";
    if (visual.mood) bg.classList.add("mood-" + visual.mood);

    // Location label
    const locIcon = this.LOCATION_ICONS[visual.location_icon] || "\u{1F4CD}";
    els.sceneLocation.textContent = locIcon + " " + (visual.location_name || "Unknown");

    // Mood icon
    els.sceneMoodIcon.textContent = this.MOOD_ICONS[visual.mood] || "\u{2728}";
  },

  getChoiceIcon(iconKey) {
    return this.CHOICE_ICONS[iconKey] || "\u{27A1}\u{FE0F}";
  },

  getItemIcon(itemName) {
    const lower = itemName.toLowerCase();
    for (const [key, icon] of Object.entries(this.ITEM_ICONS)) {
      if (lower.includes(key)) return icon;
    }
    return "\u{1F4E6}";
  },

  getAchievementIcon(name) {
    return this.ACHIEVEMENT_ICONS[name] || "\u{2B50}";
  },
};

/* ============================================================
   5. Accessibility
   ============================================================ */
const A11y = {
  el: null,
  init() { this.el = document.getElementById("sr-announcer"); },
  announce(msg) {
    if (!this.el) return;
    this.el.textContent = "";
    requestAnimationFrame(() => { this.el.textContent = msg; });
  },
};

/* ============================================================
   6. Game Controller
   ============================================================ */
const Game = {
  // State
  gameId: null,
  adventure: null,
  playerName: null,
  language: "en",
  health: 100,
  maxHealth: 100,
  inventory: [],
  turn: 0,
  xp: 0,
  achievements: [],
  mapNodes: [],
  currentNodeId: "",
  history: [],
  isLoading: false,
  typewriterTimer: null,
  typewriterResolve: null,
  typewriterSpeed: 18,

  // DOM cache
  els: {},

  init() {
    this.cacheDOM();
    this.bindEvents();
    Sound.init();
    A11y.init();
    MapRender.init(this.els.gameMap);
    this.els.playerName.focus();
  },

  cacheDOM() {
    const q = (s) => document.querySelector(s);
    this.els = {
      // Screens
      startScreen: q("#start-screen"),
      gameScreen: q("#game-screen"),
      gameoverScreen: q("#gameover-screen"),
      // Start
      playerName: q("#player-name"),
      startError: q("#start-error"),
      btnStart: q("#btn-start"),
      // Game
      heartsDisplay: q("#hearts-display"),
      healthText: q("#health-text"),
      xpValue: q("#xp-value"),
      turnCounter: q("#turn-counter"),
      narrative: q("#narrative"),
      btnNarrate: q("#btn-narrate"),
      btnHistory: q("#btn-history"),
      historyPanel: q("#history-panel"),
      historyContent: q("#history-content"),
      choices: q("#choices"),
      customAction: q("#custom-action"),
      btnCustomAction: q("#btn-custom-action"),
      loadingIndicator: q("#loading-indicator"),
      gameError: q("#game-error"),
      // Scene
      sceneCard: q("#scene-card"),
      sceneBg: q("#scene-bg"),
      sceneLocation: q("#scene-location"),
      sceneMoodIcon: q("#scene-mood-icon"),
      sceneImage: q("#scene-image"),
      // Side panels
      gameMap: q("#game-map"),
      inventoryGrid: q("#inventory-grid"),
      achievementsGrid: q("#achievements-grid"),
      // Overlays
      encounterOverlay: q("#encounter-overlay"),
      encounterIcon: q("#encounter-icon"),
      encounterName: q("#encounter-name"),
      encounterType: q("#encounter-type"),
      itemFoundOverlay: q("#item-found-overlay"),
      itemFoundName: q("#item-found-name"),
      achievementPopup: q("#achievement-popup"),
      achievementText: q("#achievement-text"),
      // Game over
      gameoverIcon: q("#gameover-icon"),
      gameoverHeading: q("#gameover-heading"),
      gameoverMessage: q("#gameover-message"),
      gameoverAchievements: q("#gameover-achievements"),
      summaryTurns: q("#summary-turns"),
      summaryHealth: q("#summary-health"),
      summaryItems: q("#summary-items"),
      summaryXp: q("#summary-xp"),
      btnPlayAgain: q("#btn-play-again"),
      // Header
      languageSelect: q("#language-select"),
      btnSoundToggle: q("#btn-sound-toggle"),
      particleOverlay: q("#particle-overlay"),
    };
  },

  bindEvents() {
    this.els.btnStart.addEventListener("click", () => this.handleStart());
    this.els.playerName.addEventListener("keydown", (e) => { if (e.key === "Enter") this.handleStart(); });
    this.els.btnCustomAction.addEventListener("click", () => this.handleCustomAction());
    this.els.customAction.addEventListener("keydown", (e) => { if (e.key === "Enter") this.handleCustomAction(); });
    this.els.btnNarrate.addEventListener("click", () => this.handleNarrate());
    this.els.btnHistory.addEventListener("click", () => this.toggleHistory());
    this.els.btnPlayAgain.addEventListener("click", () => this.handlePlayAgain());
    this.els.narrative.addEventListener("click", () => this.skipTypewriter());
    this.els.btnSoundToggle.addEventListener("click", () => this.toggleSound());
    this.els.languageSelect.addEventListener("change", (e) => { this.language = e.target.value; });

    // Keyboard shortcuts for choices
    document.addEventListener("keydown", (e) => {
      if (this.isLoading) return;
      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= 9) {
        const btns = this.els.choices.querySelectorAll(".choice-btn");
        if (btns[num - 1]) {
          btns[num - 1].click();
        }
      }
    });
  },

  /* --- Screen Management --- */
  showScreen(name) {
    [this.els.startScreen, this.els.gameScreen, this.els.gameoverScreen].forEach(s => {
      s.hidden = true;
      s.classList.remove("screen--active");
    });
    const screen = {
      start: this.els.startScreen,
      game: this.els.gameScreen,
      gameover: this.els.gameoverScreen,
    }[name];
    if (screen) {
      screen.hidden = false;
      screen.classList.add("screen--active");
      // Move focus into the new screen for keyboard / screen-reader users.
      const heading = screen.querySelector("h2");
      if (heading) heading.focus({ preventScroll: false });
    }
  },

  /* --- Start Game --- */
  async handleStart() {
    const name = this.els.playerName.value.trim();
    const adventureRadio = document.querySelector('input[name="adventure"]:checked');

    this.els.startError.hidden = true;
    if (!name) {
      this.showError(this.els.startError, "Please enter your hero name!");
      this.els.playerName.focus();
      return;
    }
    if (!adventureRadio) {
      this.showError(this.els.startError, "Please pick an adventure!");
      return;
    }

    const adventure = adventureRadio.value;
    this.playerName = name;
    this.adventure = adventure;
    this.setLoading(true);

    try {
      const data = await API.startGame(name, adventure, this.language);
      this.gameId = data.game_id;
      this.health = data.health;
      this.inventory = data.inventory || [];
      this.turn = data.turn_count;
      this.xp = data.xp || 0;
      this.achievements = data.achievements || [];
      this.mapNodes = data.map_nodes || [];
      this.currentNodeId = data.current_node_id || "";
      this.history = [{ turn: 1, narrative: data.narrative, action: null }];

      this.applyTheme(adventure);
      this.showScreen("game");
      this.updateHearts(data.health);
      this.updateXP(data.xp || 0);
      this.updateTurn(data.turn_count);
      this.updateInventory(data.inventory || []);
      this.updateAchievements(data.achievements || []);
      MapRender.render(this.mapNodes, this.currentNodeId);

      if (data.scene_visual) {
        Scene.renderSceneCard(data.scene_visual, this.els);
      }

      await this.typewrite(data.narrative);
      this.renderChoices(data.choices, data.choice_icons || []);
      A11y.announce("Your adventure has begun! " + data.narrative.slice(0, 100));
      Sound.click();
    } catch (err) {
      this.showError(this.els.startError, err.message);
    } finally {
      this.setLoading(false);
    }
  },

  /* --- Actions --- */
  handleChoiceAction(text) {
    if (this.isLoading) return;
    Sound.click();
    this.sendAction(text);
  },

  handleCustomAction() {
    const action = this.els.customAction.value.trim();
    if (!action || this.isLoading) return;
    Sound.click();
    this.els.customAction.value = "";
    this.sendAction(action);
  },

  async sendAction(action) {
    this.setLoading(true);
    this.els.choices.innerHTML = "";
    const prevAchievements = [...this.achievements];

    try {
      const data = await API.sendAction(this.gameId, action);
      const prevHealth = this.health;

      this.health = data.health;
      this.inventory = data.inventory || [];
      this.turn = data.turn_count;
      this.xp = data.xp || 0;
      this.achievements = data.achievements || [];
      this.mapNodes = data.map_nodes || [];
      this.currentNodeId = data.current_node_id || "";
      this.history.push({ turn: data.turn_count, narrative: data.narrative, action });

      this.updateHearts(data.health);
      this.updateXP(data.xp || 0);
      this.updateTurn(data.turn_count);
      this.updateInventory(data.inventory || []);
      this.updateAchievements(data.achievements || []);
      MapRender.render(this.mapNodes, this.currentNodeId);

      if (data.scene_visual) {
        Scene.renderSceneCard(data.scene_visual, this.els);
        // Show encounter overlay for NPCs
        if (data.scene_visual.npc_name) {
          this.showEncounter(data.scene_visual);
        }
      }

      // Health effects
      if (data.health < prevHealth) {
        Sound.damage();
        this.shakeScreen();
      } else if (data.health > prevHealth) {
        Sound.heal();
      }

      // New items — show the item-found overlay for any item_found in scene_visual.
      if (data.scene_visual && data.scene_visual.item_found) {
        this.showItemFound(data.scene_visual.item_found);
      }

      // New achievements
      const newAchievements = (data.achievements || []).filter(a => !prevAchievements.includes(a));
      newAchievements.forEach((a, i) => {
        setTimeout(() => this.showAchievementPopup(a), i * 1500);
      });

      // Narrative
      await this.typewrite(data.narrative);

      // Game over check
      if (!data.is_alive || data.is_complete) {
        this.handleGameOver(data);
        return;
      }

      this.renderChoices(data.choices, data.choice_icons || []);
      A11y.announce(`Turn ${data.turn_count}. ${data.narrative.slice(0, 100)}`);
    } catch (err) {
      this.showError(this.els.gameError, err.message);
    } finally {
      this.setLoading(false);
    }
  },

  /* --- Game Over --- */
  handleGameOver(data) {
    const isVictory = data.is_alive && data.is_complete;
    if (isVictory) {
      Sound.victory();
      this.els.gameoverIcon.textContent = "\u{1F3C6}";
      this.els.gameoverHeading.textContent = "Victory!";
      this.els.gameoverMessage.textContent = "You completed the adventure! You're a true hero!";
    } else {
      Sound.defeat();
      this.els.gameoverIcon.textContent = "\u{1F47B}";
      this.els.gameoverHeading.textContent = "Game Over";
      this.els.gameoverMessage.textContent = "The adventure ends here... but heroes never give up!";
    }

    this.els.summaryTurns.textContent = this.turn;
    this.els.summaryHealth.textContent = this.health;
    this.els.summaryItems.textContent = this.inventory.length;
    this.els.summaryXp.textContent = this.xp;

    // Show earned achievements
    this.els.gameoverAchievements.innerHTML = "";
    this.achievements.forEach(a => {
      const badge = document.createElement("span");
      badge.className = "achievement-badge";
      badge.innerHTML = `<span class="achievement-badge-icon">${Scene.getAchievementIcon(a)}</span> ${a}`;
      this.els.gameoverAchievements.appendChild(badge);
    });

    setTimeout(() => this.showScreen("gameover"), 1500);
    A11y.announce(isVictory ? "Victory! You completed the adventure!" : "Game over. Try again!");
  },

  handlePlayAgain() {
    Sound.click();
    this.gameId = null;
    this.health = 100;
    this.inventory = [];
    this.turn = 0;
    this.xp = 0;
    this.achievements = [];
    this.mapNodes = [];
    this.currentNodeId = "";
    this.history = [];
    this.cancelTypewriter();

    // Reset UI
    document.body.className = "";
    this.els.narrative.innerHTML = '<p class="narrative-placeholder">Your adventure awaits...</p>';
    this.els.choices.innerHTML = "";
    this.els.inventoryGrid.innerHTML = '<span class="inventory-empty" role="listitem">Empty backpack</span>';
    this.els.achievementsGrid.innerHTML = '<span class="achievements-empty" role="listitem">No badges yet</span>';
    this.els.sceneImage.hidden = true;
    this.els.historyPanel.hidden = true;
    this.els.btnHistory.setAttribute("aria-expanded", "false");

    this.showScreen("start");
    this.els.playerName.focus();
  },

  /* --- Typewriter --- */
  async typewrite(text) {
    this.cancelTypewriter();

    // Add separator if there's existing content
    const hasContent = this.els.narrative.querySelector(".narrative-entry");
    if (hasContent) {
      const sep = document.createElement("hr");
      sep.className = "narrative-separator";
      this.els.narrative.appendChild(sep);
    }

    const entry = document.createElement("div");
    entry.className = "narrative-entry";
    this.els.narrative.appendChild(entry);

    // Remove placeholder
    const placeholder = this.els.narrative.querySelector(".narrative-placeholder");
    if (placeholder) placeholder.remove();

    return new Promise((resolve) => {
      this.typewriterResolve = resolve;
      let i = 0;
      const cursor = document.createElement("span");
      cursor.className = "typewriter-cursor";
      entry.appendChild(cursor);

      this.typewriterTimer = setInterval(() => {
        if (i < text.length) {
          cursor.before(document.createTextNode(text[i]));
          i++;
          this.els.narrative.scrollTop = this.els.narrative.scrollHeight;
        } else {
          clearInterval(this.typewriterTimer);
          this.typewriterTimer = null;
          cursor.remove();
          this.typewriterResolve = null;
          resolve();
        }
      }, this.typewriterSpeed);
    });
  },

  skipTypewriter() {
    if (!this.typewriterTimer) return;
    clearInterval(this.typewriterTimer);
    this.typewriterTimer = null;
    const cursor = this.els.narrative.querySelector(".typewriter-cursor");
    if (cursor) cursor.remove();
    if (this.typewriterResolve) {
      this.typewriterResolve();
      this.typewriterResolve = null;
    }
    // Fill remaining text from last history entry
    const lastEntry = this.els.narrative.querySelector(".narrative-entry:last-child");
    if (lastEntry && this.history.length > 0) {
      const lastText = this.history[this.history.length - 1].narrative;
      lastEntry.textContent = lastText;
    }
  },

  cancelTypewriter() {
    if (this.typewriterTimer) {
      clearInterval(this.typewriterTimer);
      this.typewriterTimer = null;
    }
    if (this.typewriterResolve) {
      this.typewriterResolve();
      this.typewriterResolve = null;
    }
  },

  /* --- UI Updates --- */
  updateHearts(health) {
    const hearts = this.els.heartsDisplay.querySelectorAll(".heart");
    const pct = health / this.maxHealth;
    hearts.forEach((heart, i) => {
      const threshold = (i + 1) / hearts.length;
      heart.className = "heart";
      if (pct >= threshold) {
        heart.classList.add("heart--full");
        heart.textContent = "\u2764\uFE0F";
      } else if (pct >= threshold - (1 / hearts.length / 2)) {
        heart.classList.add("heart--half");
        heart.textContent = "\u2764\uFE0F";
      } else {
        heart.classList.add("heart--empty");
        heart.textContent = "\u{1F5A4}";
      }
    });
    this.els.healthText.textContent = health;
    this.els.heartsDisplay.setAttribute("aria-valuenow", health);

    // Color the health number
    if (health > 60) this.els.healthText.style.color = "var(--color-neon-green)";
    else if (health > 30) this.els.healthText.style.color = "var(--color-neon-yellow)";
    else this.els.healthText.style.color = "var(--color-danger)";
  },

  updateXP(xp) {
    this.els.xpValue.textContent = xp;
  },

  updateTurn(turn) {
    this.els.turnCounter.textContent = turn;
  },

  updateInventory(items) {
    this.els.inventoryGrid.innerHTML = "";
    if (!items || items.length === 0) {
      this.els.inventoryGrid.innerHTML = '<span class="inventory-empty" role="listitem">Empty backpack</span>';
      return;
    }
    items.forEach(item => {
      const div = document.createElement("div");
      div.className = "inventory-item";
      div.setAttribute("role", "listitem");
      div.innerHTML = `<span class="inventory-item-icon">${Scene.getItemIcon(item)}</span><span class="inventory-item-name">${this.escapeHtml(item)}</span>`;
      this.els.inventoryGrid.appendChild(div);
    });
  },

  updateAchievements(achievements) {
    this.els.achievementsGrid.innerHTML = "";
    if (!achievements || achievements.length === 0) {
      this.els.achievementsGrid.innerHTML = '<span class="achievements-empty" role="listitem">No badges yet</span>';
      return;
    }
    achievements.forEach(name => {
      const badge = document.createElement("span");
      badge.className = "achievement-badge";
      badge.setAttribute("role", "listitem");
      badge.innerHTML = `<span class="achievement-badge-icon">${Scene.getAchievementIcon(name)}</span> ${this.escapeHtml(name)}`;
      this.els.achievementsGrid.appendChild(badge);
    });
  },

  renderChoices(choices, icons) {
    this.els.choices.innerHTML = "";
    if (!choices || choices.length === 0) return;
    choices.forEach((text, i) => {
      const btn = document.createElement("button");
      btn.className = "choice-btn";
      btn.type = "button";
      const iconKey = icons[i] || "";
      const iconEmoji = Scene.getChoiceIcon(iconKey);
      btn.innerHTML = `<span class="choice-number">${i + 1}</span><span class="choice-icon">${iconEmoji}</span><span class="choice-text">${this.escapeHtml(text)}</span>`;
      btn.setAttribute("aria-label", `Choice ${i + 1}: ${text}`);
      btn.addEventListener("click", () => this.handleChoiceAction(text));
      this.els.choices.appendChild(btn);
    });
  },

  /* --- Overlays --- */
  showEncounter(visual) {
    const npcIcons = { friendly: "\u{1F91D}", hostile: "\u{1F47E}", neutral: "\u{1F464}" };
    this.els.encounterIcon.textContent = npcIcons[visual.npc_type] || "\u{1F464}";
    this.els.encounterName.textContent = visual.npc_name;
    this.els.encounterType.textContent = visual.npc_type || "unknown";
    this.els.encounterOverlay.hidden = false;
    setTimeout(() => { this.els.encounterOverlay.hidden = true; }, 2500);
  },

  showItemFound(itemName) {
    this.els.itemFoundName.textContent = itemName;
    this.els.itemFoundOverlay.hidden = false;
    Sound.item();
    setTimeout(() => { this.els.itemFoundOverlay.hidden = true; }, 2500);
  },

  showAchievementPopup(name) {
    this.els.achievementText.textContent = `Badge: ${name}!`;
    this.els.achievementPopup.hidden = false;
    Sound.achieve();
    A11y.announce(`Achievement unlocked: ${name}`);
    setTimeout(() => { this.els.achievementPopup.hidden = true; }, 3000);
  },

  /* --- Effects --- */
  shakeScreen() {
    const el = this.els.gameScreen;
    el.classList.add("screen-shake");
    setTimeout(() => el.classList.remove("screen-shake"), 500);
  },

  /* --- Narration (TTS) --- */
  async handleNarrate() {
    const text = this.history.length > 0 ? this.history[this.history.length - 1].narrative : "";
    if (!text) return;

    this.els.btnNarrate.disabled = true;
    this.els.btnNarrate.textContent = "Playing...";

    try {
      // Translate if needed
      let narrateText = text;
      if (this.language !== "en") {
        const result = await API.translateText(text, this.language);
        if (result) narrateText = result.translated_text;
      }

      const audio = await API.narrateAudio(narrateText);
      if (audio) {
        const audioEl = new Audio("data:audio/mp3;base64," + audio);
        audioEl.play();
        audioEl.addEventListener("ended", () => {
          this.els.btnNarrate.disabled = false;
          this.els.btnNarrate.innerHTML = '<span aria-hidden="true">&#128266;</span> Listen';
        });
      } else {
        this.els.btnNarrate.disabled = false;
        this.els.btnNarrate.innerHTML = '<span aria-hidden="true">&#128266;</span> Listen';
      }
    } catch (_) {
      this.els.btnNarrate.disabled = false;
      this.els.btnNarrate.innerHTML = '<span aria-hidden="true">&#128266;</span> Listen';
    }
  },

  /* --- History --- */
  toggleHistory() {
    const open = this.els.historyPanel.hidden;
    this.els.historyPanel.hidden = !open;
    this.els.btnHistory.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) this.renderHistory();
  },

  renderHistory() {
    this.els.historyContent.innerHTML = "";
    this.history.forEach(entry => {
      const div = document.createElement("div");
      div.className = "history-entry";
      let html = `<div class="history-turn">Turn ${entry.turn}</div>`;
      if (entry.action) html += `<div class="history-action">You chose: ${this.escapeHtml(entry.action)}</div>`;
      html += `<div class="history-narrative">${this.escapeHtml(entry.narrative.slice(0, 200))}${entry.narrative.length > 200 ? "..." : ""}</div>`;
      div.innerHTML = html;
      this.els.historyContent.appendChild(div);
    });
  },

  /* --- Theme --- */
  applyTheme(adventure) {
    document.body.className = "";
    document.body.classList.add("theme-" + adventure);
  },

  /* --- Sound Toggle --- */
  toggleSound() {
    Sound.enabled = !Sound.enabled;
    const btn = this.els.btnSoundToggle;
    btn.setAttribute("aria-pressed", Sound.enabled ? "true" : "false");
    btn.querySelector(".sound-icon").textContent = Sound.enabled ? "\u{1F50A}" : "\u{1F507}";
  },

  /* --- Loading --- */
  setLoading(loading) {
    this.isLoading = loading;
    this.els.loadingIndicator.hidden = !loading;
    this.els.btnStart.disabled = loading;
    this.els.btnCustomAction.disabled = loading;
    if (loading) {
      this.els.choices.querySelectorAll(".choice-btn").forEach(b => b.disabled = true);
    }
  },

  /* --- Error --- */
  showError(el, message) {
    el.textContent = message;
    el.hidden = false;
    setTimeout(() => { el.hidden = true; }, 8000);
  },

  /* --- Util --- */
  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  },
};

/* ============================================================
   Bootstrap
   ============================================================ */
document.addEventListener("DOMContentLoaded", () => {
  Game.init();
});
