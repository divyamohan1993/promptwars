/**
 * QuestForge — AI-Powered Text Adventure
 * Frontend Application (Vanilla JS)
 *
 * Handles:
 *  - API communication with the backend
 *  - Screen management (start, game, gameover)
 *  - Narrative rendering with typewriter effect
 *  - Health, inventory, and turn tracking
 *  - Genre-themed styling
 *  - Accessibility: focus management, aria-live announcements
 */

/* ============================================================
   1. API Client
   ============================================================ */

const API = {
  /**
   * Start a new game session.
   * @param {string} playerName
   * @param {string} genre
   * @returns {Promise<Object>} Game state from server
   */
  async startGame(playerName, genre) {
    const response = await fetch('/api/game/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: playerName, genre: genre }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Server error (${response.status})`);
    }
    return response.json();
  },

  /**
   * Send a player action (choice or free input).
   * @param {string} gameId
   * @param {string} action
   * @returns {Promise<Object>} Updated game state
   */
  async sendAction(gameId, action) {
    const response = await fetch('/api/game/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game_id: gameId, action: action }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Server error (${response.status})`);
    }
    return response.json();
  },

  /**
   * Retrieve current game state.
   * @param {string} gameId
   * @returns {Promise<Object>} Current game state
   */
  async getGameState(gameId) {
    const response = await fetch(`/api/game/${encodeURIComponent(gameId)}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Server error (${response.status})`);
    }
    return response.json();
  },
};

/* ============================================================
   2. Game Controller
   ============================================================ */

const Game = {
  // State
  gameId: null,
  genre: null,
  playerName: null,
  health: 100,
  maxHealth: 100,
  inventory: [],
  turn: 0,
  history: [],          // Array of { turn, narrative, action }
  isLoading: false,
  typewriterTimer: null, // For cancelling typewriter
  typewriterResolve: null,
  typewriterSpeed: 20,   // ms per character

  /* ----------------------------------------------------------
     2a. Initialization
     ---------------------------------------------------------- */

  init() {
    this.cacheDOM();
    this.bindEvents();
    this.showScreen('start');
  },

  cacheDOM() {
    // Screens
    this.screens = {
      start:    document.getElementById('start-screen'),
      game:     document.getElementById('game-screen'),
      gameover: document.getElementById('gameover-screen'),
    };

    // Start screen elements
    this.els = {
      playerNameInput:  document.getElementById('player-name'),
      genreCards:        document.querySelectorAll('.genre-card'),
      genreRadios:       document.querySelectorAll('.genre-radio'),
      btnStart:          document.getElementById('btn-start'),
      startError:        document.getElementById('start-error'),

      // Game screen
      healthBar:         document.getElementById('health-bar'),
      healthBarWrapper:  document.querySelector('.health-bar-wrapper'),
      healthText:        document.getElementById('health-text'),
      inventory:         document.getElementById('inventory'),
      turnCounter:       document.getElementById('turn-counter'),
      narrative:         document.getElementById('narrative'),
      choices:           document.getElementById('choices'),
      customActionInput: document.getElementById('custom-action'),
      btnCustomAction:   document.getElementById('btn-custom-action'),
      btnHistory:        document.getElementById('btn-history'),
      historyPanel:      document.getElementById('history-panel'),
      historyContent:    document.getElementById('history-content'),
      loadingIndicator:  document.getElementById('loading-indicator'),
      gameError:         document.getElementById('game-error'),

      // Game over screen
      gameoverCard:     document.querySelector('.gameover-card'),
      gameoverIcon:     document.getElementById('gameover-icon'),
      gameoverHeading:  document.getElementById('gameover-heading'),
      gameoverMessage:  document.getElementById('gameover-message'),
      summaryTurns:     document.getElementById('summary-turns'),
      summaryHealth:    document.getElementById('summary-health'),
      summaryItems:     document.getElementById('summary-items'),
      summaryGenre:     document.getElementById('summary-genre'),
      btnPlayAgain:     document.getElementById('btn-play-again'),

      // Accessibility
      srAnnouncer:      document.getElementById('sr-announcer'),
    };
  },

  /* ----------------------------------------------------------
     2b. Event Binding
     ---------------------------------------------------------- */

  bindEvents() {
    // Genre card selection — add .selected class for CSS fallback
    this.els.genreCards.forEach((card) => {
      card.addEventListener('click', () => {
        this.els.genreCards.forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
        const radio = card.querySelector('.genre-radio');
        if (radio) radio.checked = true;
      });
    });

    // Also handle radio change (keyboard navigation)
    this.els.genreRadios.forEach((radio) => {
      radio.addEventListener('change', () => {
        this.els.genreCards.forEach((c) => c.classList.remove('selected'));
        const parentCard = radio.closest('.genre-card');
        if (parentCard) parentCard.classList.add('selected');
      });
    });

    // Start game
    this.els.btnStart.addEventListener('click', () => this.handleStartGame());

    // Allow Enter key on name input to start game
    this.els.playerNameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.handleStartGame();
    });

    // Custom action
    this.els.btnCustomAction.addEventListener('click', () => this.handleCustomAction());
    this.els.customActionInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.handleCustomAction();
    });

    // History toggle
    this.els.btnHistory.addEventListener('click', () => this.toggleHistory());

    // Play again
    this.els.btnPlayAgain.addEventListener('click', () => this.handlePlayAgain());

    // Click on narrative to skip typewriter
    this.els.narrative.addEventListener('click', () => this.skipTypewriter());
  },

  /* ----------------------------------------------------------
     2c. Screen Management
     ---------------------------------------------------------- */

  showScreen(name) {
    Object.entries(this.screens).forEach(([key, el]) => {
      if (key === name) {
        el.hidden = false;
        el.classList.add('screen--active');
      } else {
        el.hidden = true;
        el.classList.remove('screen--active');
      }
    });

    // Focus management for accessibility
    requestAnimationFrame(() => {
      switch (name) {
        case 'start':
          this.els.playerNameInput.focus();
          break;
        case 'game':
          this.els.narrative.focus();
          break;
        case 'gameover':
          this.els.gameoverHeading.setAttribute('tabindex', '-1');
          this.els.gameoverHeading.focus();
          break;
      }
    });
  },

  /* ----------------------------------------------------------
     2d. Start Game Handler
     ---------------------------------------------------------- */

  async handleStartGame() {
    // Validate
    const name = this.els.playerNameInput.value.trim();
    const selectedRadio = document.querySelector('.genre-radio:checked');

    if (!name) {
      this.showStartError('Please enter your adventurer name.');
      this.els.playerNameInput.focus();
      return;
    }

    if (!selectedRadio) {
      this.showStartError('Please choose a genre for your adventure.');
      return;
    }

    const genre = selectedRadio.value;
    this.hideStartError();

    // Disable start button
    this.els.btnStart.disabled = true;
    this.els.btnStart.querySelector('.btn-text').textContent = 'Summoning your quest...';

    try {
      const data = await API.startGame(name, genre);

      // Set state
      this.gameId = data.game_id;
      this.genre = genre;
      this.playerName = name;
      this.health = data.health != null ? data.health : 100;
      this.maxHealth = 100;
      this.inventory = data.inventory || [];
      this.turn = data.turn_count || 1;
      this.history = [];

      // Apply theme
      this.applyGenreTheme(genre);

      // Switch to game screen
      this.showScreen('game');

      // Render initial state
      this.updateHealth(this.health);
      this.updateInventory(this.inventory);
      this.updateTurn(this.turn);

      // Clear narrative and render first narrative
      this.els.narrative.innerHTML = '';
      if (data.narrative) {
        this.history.push({
          turn: this.turn,
          narrative: data.narrative,
          action: null,
        });
        await this.typewriteNarrative(data.narrative);
      }

      // Render choices
      if (data.choices && data.choices.length > 0) {
        this.renderChoices(data.choices);
      }

      this.announce(`Your ${genre} adventure has begun. ${data.narrative || ''}`);

    } catch (error) {
      this.showStartError(error.message || 'Failed to start the game. Please try again.');
    } finally {
      this.els.btnStart.disabled = false;
      this.els.btnStart.querySelector('.btn-text').textContent = 'Begin Quest';
    }
  },

  /* ----------------------------------------------------------
     2e. Action Handlers
     ---------------------------------------------------------- */

  async handleChoiceAction(choiceText) {
    if (this.isLoading) return;
    await this.sendPlayerAction(choiceText);
  },

  async handleCustomAction() {
    if (this.isLoading) return;
    const action = this.els.customActionInput.value.trim();
    if (!action) {
      this.els.customActionInput.focus();
      return;
    }
    this.els.customActionInput.value = '';
    await this.sendPlayerAction(action);
  },

  async sendPlayerAction(action) {
    this.setLoading(true);
    this.hideGameError();

    try {
      const data = await API.sendAction(this.gameId, action);

      // Update state
      this.health = data.health != null ? data.health : this.health;
      this.inventory = data.inventory || this.inventory;
      this.turn = data.turn_count || this.turn + 1;

      this.updateHealth(this.health);
      this.updateInventory(this.inventory);
      this.updateTurn(this.turn);

      // Add separator and new narrative
      if (data.narrative) {
        this.history.push({
          turn: this.turn,
          narrative: data.narrative,
          action: action,
        });
        this.addNarrativeSeparator();
        await this.typewriteNarrative(data.narrative);
      }

      // Check for game over
      if (!data.is_alive || data.is_complete) {
        this.handleGameOver(data);
        return;
      }

      // Render new choices
      if (data.choices && data.choices.length > 0) {
        this.renderChoices(data.choices);
      } else {
        this.els.choices.innerHTML = '';
      }

      this.announce(`Turn ${this.turn}. ${data.narrative || ''}`);

    } catch (error) {
      this.showGameError(error.message || 'Something went wrong. Please try again.');
    } finally {
      this.setLoading(false);
    }
  },

  /* ----------------------------------------------------------
     2f. Game Over
     ---------------------------------------------------------- */

  handleGameOver(data) {
    const isVictory = data.is_alive && data.is_complete;

    // Update gameover card
    this.els.gameoverCard.className = 'gameover-card ' +
      (isVictory ? 'gameover--victory' : 'gameover--death');

    this.els.gameoverIcon.textContent = isVictory ? '\u{1F3C6}' : '\u{1F480}';

    this.els.gameoverHeading.textContent = isVictory
      ? 'Victory! Quest Complete!'
      : 'You Have Fallen...';

    this.els.gameoverMessage.textContent = data.narrative ||
      (isVictory
        ? 'Congratulations! You have completed your quest with honor.'
        : 'Your adventure has come to a tragic end.');

    // Stats summary
    this.els.summaryTurns.textContent = this.turn;
    this.els.summaryHealth.textContent = Math.max(0, this.health);
    this.els.summaryItems.textContent = this.inventory.length;
    this.els.summaryGenre.textContent = this.formatGenreName(this.genre);

    this.showScreen('gameover');
    this.announce(
      isVictory
        ? 'Victory! You completed the quest.'
        : 'Game over. You have fallen.'
    );
  },

  /* ----------------------------------------------------------
     2g. Play Again
     ---------------------------------------------------------- */

  handlePlayAgain() {
    // Reset state
    this.gameId = null;
    this.genre = null;
    this.playerName = null;
    this.health = 100;
    this.inventory = [];
    this.turn = 0;
    this.history = [];
    this.cancelTypewriter();

    // Remove theme
    document.body.className = '';

    // Clear UI
    this.els.narrative.innerHTML = '<p class="narrative-placeholder">Your adventure awaits...</p>';
    this.els.choices.innerHTML = '';
    this.els.customActionInput.value = '';
    this.els.historyPanel.hidden = true;
    this.els.btnHistory.setAttribute('aria-expanded', 'false');
    this.els.historyContent.innerHTML = '';
    this.hideGameError();

    // Reset genre selection
    this.els.genreCards.forEach((c) => c.classList.remove('selected'));
    this.els.genreRadios.forEach((r) => { r.checked = false; });
    this.els.playerNameInput.value = '';

    // Reset stats display
    this.updateHealth(100);
    this.updateInventory([]);
    this.updateTurn(0);

    this.showScreen('start');
    this.announce('Starting a new adventure. Enter your name and choose a genre.');
  },

  /* ----------------------------------------------------------
     2h. Typewriter Effect
     ---------------------------------------------------------- */

  /**
   * Render text character-by-character into the narrative area.
   * Returns a promise that resolves when complete (or skipped).
   * @param {string} text
   * @returns {Promise<void>}
   */
  typewriteNarrative(text) {
    return new Promise((resolve) => {
      this.cancelTypewriter();

      const p = document.createElement('p');
      p.classList.add('narrative-entry');
      const textNode = document.createTextNode('');
      p.appendChild(textNode);

      // Cursor element
      const cursor = document.createElement('span');
      cursor.classList.add('typewriter-cursor');
      cursor.setAttribute('aria-hidden', 'true');
      p.appendChild(cursor);

      this.els.narrative.appendChild(p);
      this.scrollNarrativeToBottom();

      const chars = Array.from(text);
      let index = 0;

      this.typewriterResolve = () => {
        // Complete the text instantly
        textNode.textContent = text;
        cursor.remove();
        this.scrollNarrativeToBottom();
        resolve();
      };

      const tick = () => {
        if (index < chars.length) {
          textNode.textContent += chars[index];
          index++;
          this.scrollNarrativeToBottom();
          this.typewriterTimer = setTimeout(tick, this.typewriterSpeed);
        } else {
          // Finished naturally
          cursor.remove();
          this.typewriterTimer = null;
          this.typewriterResolve = null;
          resolve();
        }
      };

      tick();
    });
  },

  skipTypewriter() {
    if (this.typewriterResolve) {
      clearTimeout(this.typewriterTimer);
      this.typewriterTimer = null;
      const fn = this.typewriterResolve;
      this.typewriterResolve = null;
      fn();
    }
  },

  cancelTypewriter() {
    if (this.typewriterTimer) {
      clearTimeout(this.typewriterTimer);
      this.typewriterTimer = null;
    }
    this.typewriterResolve = null;
  },

  addNarrativeSeparator() {
    const hr = document.createElement('hr');
    hr.classList.add('narrative-separator');
    hr.setAttribute('aria-hidden', 'true');
    this.els.narrative.appendChild(hr);
  },

  scrollNarrativeToBottom() {
    const el = this.els.narrative;
    el.scrollTop = el.scrollHeight;
  },

  /* ----------------------------------------------------------
     2i. UI Update Helpers
     ---------------------------------------------------------- */

  updateHealth(value) {
    this.health = Math.max(0, Math.min(value, this.maxHealth));
    const pct = Math.round((this.health / this.maxHealth) * 100);

    this.els.healthBar.style.width = pct + '%';
    this.els.healthText.textContent = this.health;

    // Update ARIA
    this.els.healthBarWrapper.setAttribute('aria-valuenow', this.health);

    // Color class
    this.els.healthBar.classList.remove('health--high', 'health--mid', 'health--low');
    if (pct > 60) {
      this.els.healthBar.classList.add('health--high');
    } else if (pct > 30) {
      this.els.healthBar.classList.add('health--mid');
    } else {
      this.els.healthBar.classList.add('health--low');
    }
  },

  updateInventory(items) {
    this.inventory = items;
    const container = this.els.inventory;
    container.innerHTML = '';

    if (!items || items.length === 0) {
      const empty = document.createElement('span');
      empty.className = 'inventory-empty';
      empty.setAttribute('role', 'listitem');
      empty.textContent = 'Empty';
      container.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const chip = document.createElement('span');
      chip.className = 'inventory-item';
      chip.setAttribute('role', 'listitem');
      chip.textContent = item;
      container.appendChild(chip);
    });
  },

  updateTurn(turn) {
    this.turn = turn;
    this.els.turnCounter.textContent = turn;
  },

  renderChoices(choices) {
    const container = this.els.choices;
    container.innerHTML = '';

    choices.forEach((choiceText, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'choice-btn';
      btn.disabled = this.isLoading;
      btn.setAttribute('aria-label', `Choice ${i + 1}: ${choiceText}`);

      const num = document.createElement('span');
      num.className = 'choice-number';
      num.setAttribute('aria-hidden', 'true');
      num.textContent = i + 1;

      const text = document.createElement('span');
      text.className = 'choice-text';
      text.textContent = choiceText;

      btn.appendChild(num);
      btn.appendChild(text);

      btn.addEventListener('click', () => this.handleChoiceAction(choiceText));

      container.appendChild(btn);
    });

    // Focus first choice for accessibility
    requestAnimationFrame(() => {
      const first = container.querySelector('.choice-btn');
      if (first) first.focus();
    });
  },

  /* ----------------------------------------------------------
     2j. Loading State
     ---------------------------------------------------------- */

  setLoading(loading) {
    this.isLoading = loading;

    // Show/hide spinner
    this.els.loadingIndicator.hidden = !loading;

    // Disable/enable interactive elements
    const choiceBtns = this.els.choices.querySelectorAll('.choice-btn');
    choiceBtns.forEach((btn) => { btn.disabled = loading; });

    this.els.btnCustomAction.disabled = loading;
    this.els.customActionInput.disabled = loading;

    if (loading) {
      this.els.choices.classList.add('actions-disabled');
    } else {
      this.els.choices.classList.remove('actions-disabled');
    }
  },

  /* ----------------------------------------------------------
     2k. History
     ---------------------------------------------------------- */

  toggleHistory() {
    const panel = this.els.historyPanel;
    const isOpen = !panel.hidden;

    if (isOpen) {
      panel.hidden = true;
      this.els.btnHistory.setAttribute('aria-expanded', 'false');
    } else {
      this.renderHistory();
      panel.hidden = false;
      this.els.btnHistory.setAttribute('aria-expanded', 'true');
      panel.focus();
    }
  },

  renderHistory() {
    const container = this.els.historyContent;
    container.innerHTML = '';

    if (this.history.length === 0) {
      container.textContent = 'No history yet.';
      return;
    }

    this.history.forEach((entry) => {
      const div = document.createElement('div');
      div.className = 'history-entry';

      const label = document.createElement('span');
      label.className = 'history-turn-label';
      label.textContent = `Turn ${entry.turn}`;
      div.appendChild(label);

      if (entry.action) {
        const action = document.createElement('div');
        action.className = 'history-action';
        action.textContent = `Action: ${entry.action}`;
        div.appendChild(action);
      }

      const narr = document.createElement('div');
      narr.textContent = entry.narrative;
      div.appendChild(narr);

      container.appendChild(div);
    });
  },

  /* ----------------------------------------------------------
     2l. Genre Theme
     ---------------------------------------------------------- */

  applyGenreTheme(genre) {
    // Remove all existing theme classes
    document.body.classList.remove(
      'theme-fantasy', 'theme-sci-fi', 'theme-mystery',
      'theme-horror', 'theme-pirate'
    );
    if (genre) {
      document.body.classList.add(`theme-${genre}`);
    }
  },

  formatGenreName(genre) {
    const names = {
      fantasy: 'Fantasy',
      'sci-fi': 'Sci-Fi',
      mystery: 'Mystery',
      horror: 'Horror',
      pirate: 'Pirate',
    };
    return names[genre] || genre || '—';
  },

  /* ----------------------------------------------------------
     2m. Error Handling
     ---------------------------------------------------------- */

  showStartError(message) {
    this.els.startError.textContent = message;
    this.els.startError.hidden = false;
    this.announce(message);
  },

  hideStartError() {
    this.els.startError.textContent = '';
    this.els.startError.hidden = true;
  },

  showGameError(message) {
    this.els.gameError.textContent = message;
    this.els.gameError.hidden = false;
    this.announce(`Error: ${message}`);
  },

  hideGameError() {
    this.els.gameError.textContent = '';
    this.els.gameError.hidden = true;
  },

  /* ----------------------------------------------------------
     2n. Accessibility — Screen Reader Announcements
     ---------------------------------------------------------- */

  announce(message) {
    const el = this.els.srAnnouncer;
    // Clear then set to trigger aria-live announcement
    el.textContent = '';
    requestAnimationFrame(() => {
      el.textContent = message;
    });
  },
};

/* ============================================================
   3. Keyboard Shortcut Support
   ============================================================ */

document.addEventListener('keydown', (e) => {
  // Number keys 1-9 to select choices quickly during game
  if (
    Game.screens.game &&
    !Game.screens.game.hidden &&
    !Game.isLoading &&
    e.key >= '1' && e.key <= '9'
  ) {
    const index = parseInt(e.key, 10) - 1;
    const choiceBtns = Game.els.choices.querySelectorAll('.choice-btn');
    if (choiceBtns[index]) {
      e.preventDefault();
      choiceBtns[index].click();
    }
  }
});

/* ============================================================
   4. Bootstrap
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  Game.init();
});
