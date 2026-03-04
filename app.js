(function () {
  var KEYS = {
    todos: 'today-todos',
    daily: 'daily-tasks',
    lastDate: 'last-loaded-date',
    supplements: 'supplements',
    suppChecks: 'supplement-checks',
    suppLastDate: 'supplement-last-date'
  };

  var todos = [];
  var dailyTasks = [];
  var currentFilter = 'all';
  var supplements = [];
  var suppChecks = {};

  var SLOT_LABELS = {
    'empty': '공복',
    'morning-before': '아침 식전',
    'morning-after': '아침 식후',
    'lunch-before': '점심 식전',
    'lunch-after': '점심 식후',
    'dinner-before': '저녁 식전',
    'dinner-after': '저녁 식후'
  };

  var SLOT_ORDER = ['empty', 'morning-before', 'morning-after', 'lunch-before', 'lunch-after', 'dinner-before', 'dinner-after'];

  // --- 날짜 유틸 ---
  function getTodayStr() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  function displayDate() {
    var el = document.getElementById('today-date');
    if (!el) return;
    var now = new Date();
    var days = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
    el.textContent = now.getFullYear() + '년 ' + (now.getMonth() + 1) + '월 ' + now.getDate() + '일 ' + days[now.getDay()];
  }

  // --- LocalStorage ---
  function save(key, data) {
    localStorage.setItem(key, JSON.stringify(data));
  }

  function load(key, fallback) {
    try {
      var data = localStorage.getItem(key);
      return data ? JSON.parse(data) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  // --- 매일 고정 할일: 날짜 변경 시 자동 추가 ---
  function checkNewDay() {
    var today = getTodayStr();
    var lastDate = localStorage.getItem(KEYS.lastDate);

    if (lastDate !== today) {
      todos = [];
      dailyTasks.forEach(function (dt) {
        todos.push({
          id: Date.now() + Math.random(),
          text: dt.text,
          completed: false,
          daily: true,
          createdAt: new Date().toISOString()
        });
      });
      save(KEYS.todos, todos);
      localStorage.setItem(KEYS.lastDate, today);
    }
  }

  // --- 영양제: 날짜 변경 시 체크 초기화 ---
  function checkNewDaySupp() {
    var today = getTodayStr();
    var lastDate = localStorage.getItem(KEYS.suppLastDate);
    if (lastDate !== today) {
      suppChecks = {};
      save(KEYS.suppChecks, suppChecks);
      localStorage.setItem(KEYS.suppLastDate, today);
    }
  }

  // --- 할일 CRUD ---
  function addTodo(text) {
    var trimmed = text.trim();
    if (!trimmed) return;
    todos.push({
      id: Date.now(),
      text: trimmed,
      completed: false,
      daily: false,
      createdAt: new Date().toISOString()
    });
    save(KEYS.todos, todos);
    updateProgress();
    renderTodos();
  }

  function deleteTodo(id) {
    todos = todos.filter(function (t) { return t.id !== id; });
    save(KEYS.todos, todos);
    updateProgress();
    renderTodos();
  }

  function toggleTodo(id) {
    todos = todos.map(function (t) {
      if (t.id === id) return Object.assign({}, t, { completed: !t.completed });
      return t;
    });
    save(KEYS.todos, todos);
    updateProgress();
    renderTodos();
  }

  // --- 할일 렌더링 ---
  function getFilteredTodos() {
    if (currentFilter === 'active') return todos.filter(function (t) { return !t.completed; });
    if (currentFilter === 'completed') return todos.filter(function (t) { return t.completed; });
    return todos;
  }

  function renderTodos() {
    var list = document.getElementById('todo-list');
    if (!list) return;
    list.innerHTML = '';

    var filtered = getFilteredTodos();

    if (filtered.length === 0) {
      var empty = document.createElement('li');
      empty.className = 'empty-msg';
      empty.textContent = currentFilter === 'all' ? '할일을 추가해보세요!' : '항목이 없습니다.';
      list.appendChild(empty);
      return;
    }

    filtered.forEach(function (todo) {
      var li = document.createElement('li');
      if (todo.completed) li.classList.add('completed');
      if (todo.daily) li.classList.add('daily-item');
      li.setAttribute('data-id', todo.id);

      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = todo.completed;

      var span = document.createElement('span');
      span.className = 'todo-text';
      span.textContent = todo.text;

      var deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-btn';
      deleteBtn.textContent = '\u2715';

      li.appendChild(checkbox);
      li.appendChild(span);
      if (todo.daily) {
        var badge = document.createElement('span');
        badge.className = 'daily-badge';
        badge.textContent = '매일';
        li.appendChild(badge);
      }
      li.appendChild(deleteBtn);
      list.appendChild(li);
    });
  }

  function updateProgress() {
    var progress = document.getElementById('progress');
    if (!progress) return;
    var total = todos.length;
    var completed = todos.filter(function (t) { return t.completed; }).length;
    var textEl = progress.querySelector('.progress-text');
    var fillEl = progress.querySelector('.progress-fill');
    if (textEl) textEl.textContent = '완료: ' + completed + '/' + total;
    if (fillEl) fillEl.style.width = total === 0 ? '0%' : Math.round((completed / total) * 100) + '%';
  }

  // --- 매일 고정 할일 관리 ---
  function addDailyTask(text) {
    var trimmed = text.trim();
    if (!trimmed) return;
    dailyTasks.push({ id: Date.now(), text: trimmed });
    save(KEYS.daily, dailyTasks);
    renderDailyTasks();
  }

  function deleteDailyTask(id) {
    dailyTasks = dailyTasks.filter(function (t) { return t.id !== id; });
    save(KEYS.daily, dailyTasks);
    renderDailyTasks();
  }

  function renderDailyTasks() {
    var list = document.getElementById('daily-list');
    if (!list) return;
    list.innerHTML = '';

    if (dailyTasks.length === 0) {
      var empty = document.createElement('li');
      empty.className = 'empty-msg';
      empty.textContent = '등록된 고정 할일이 없습니다.';
      list.appendChild(empty);
      return;
    }

    dailyTasks.forEach(function (task) {
      var li = document.createElement('li');
      li.setAttribute('data-id', task.id);

      var span = document.createElement('span');
      span.className = 'daily-task-text';
      span.textContent = task.text;

      var deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-btn';
      deleteBtn.textContent = '\u2715';

      li.appendChild(span);
      li.appendChild(deleteBtn);
      list.appendChild(li);
    });
  }

  // --- 영양제 CRUD ---
  function addSupplement(name, slot) {
    var trimmed = name.trim();
    if (!trimmed) return;
    supplements.push({
      id: Date.now(),
      name: trimmed,
      slot: slot
    });
    save(KEYS.supplements, supplements);
    renderSuppChecklist();
    renderSuppList();
    updateSuppProgress();
  }

  function deleteSupplement(id) {
    supplements = supplements.filter(function (s) { return s.id !== id; });
    delete suppChecks[id];
    save(KEYS.supplements, supplements);
    save(KEYS.suppChecks, suppChecks);
    renderSuppChecklist();
    renderSuppList();
    updateSuppProgress();
  }

  function toggleSuppCheck(id) {
    suppChecks[id] = !suppChecks[id];
    save(KEYS.suppChecks, suppChecks);
    renderSuppChecklist();
    updateSuppProgress();
  }

  // --- 영양제 렌더링 ---
  function renderSuppChecklist() {
    var container = document.getElementById('supp-checklist');
    if (!container) return;
    container.innerHTML = '';

    if (supplements.length === 0) {
      var empty = document.createElement('div');
      empty.className = 'empty-msg';
      empty.style.padding = '40px 0';
      empty.textContent = '아래 영양제 관리에서 등록해보세요!';
      container.appendChild(empty);
      return;
    }

    // 슬롯별 그룹핑
    var groups = {};
    supplements.forEach(function (supp) {
      if (!groups[supp.slot]) groups[supp.slot] = [];
      groups[supp.slot].push(supp);
    });

    SLOT_ORDER.forEach(function (slot) {
      if (!groups[slot]) return;

      var group = document.createElement('div');
      group.className = 'supp-group';

      var header = document.createElement('div');
      header.className = 'supp-group-header';
      header.textContent = SLOT_LABELS[slot];
      group.appendChild(header);

      groups[slot].forEach(function (supp) {
        var item = document.createElement('div');
        item.className = 'supp-item';
        if (suppChecks[supp.id]) item.classList.add('checked');

        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = !!suppChecks[supp.id];
        checkbox.addEventListener('change', (function (id) {
          return function () { toggleSuppCheck(id); };
        })(supp.id));

        var name = document.createElement('span');
        name.className = 'supp-name';
        name.textContent = supp.name;

        item.appendChild(checkbox);
        item.appendChild(name);
        group.appendChild(item);
      });

      container.appendChild(group);
    });
  }

  function renderSuppList() {
    var list = document.getElementById('supp-list');
    if (!list) return;
    list.innerHTML = '';

    if (supplements.length === 0) {
      var empty = document.createElement('li');
      empty.className = 'empty-msg';
      empty.textContent = '등록된 영양제가 없습니다.';
      list.appendChild(empty);
      return;
    }

    var sorted = supplements.slice().sort(function (a, b) {
      return SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot);
    });

    sorted.forEach(function (supp) {
      var li = document.createElement('li');
      li.setAttribute('data-id', supp.id);

      var name = document.createElement('span');
      name.className = 'daily-task-text';
      name.textContent = supp.name;

      var badge = document.createElement('span');
      badge.className = 'supp-slot-badge';
      badge.textContent = SLOT_LABELS[supp.slot];

      var deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-btn';
      deleteBtn.textContent = '\u2715';

      li.appendChild(name);
      li.appendChild(badge);
      li.appendChild(deleteBtn);
      list.appendChild(li);
    });
  }

  function updateSuppProgress() {
    var progress = document.getElementById('supp-progress');
    if (!progress) return;
    var total = supplements.length;
    var checked = supplements.filter(function (s) { return !!suppChecks[s.id]; }).length;
    var textEl = progress.querySelector('.progress-text');
    var fillEl = progress.querySelector('.progress-fill');
    if (textEl) textEl.textContent = '복용: ' + checked + '/' + total;
    if (fillEl) fillEl.style.width = total === 0 ? '0%' : Math.round((checked / total) * 100) + '%';
  }

  // --- 이벤트 ---
  function initEvents() {
    var form = document.getElementById('todo-form');
    var input = document.getElementById('todo-input');
    var list = document.getElementById('todo-list');
    var dailyForm = document.getElementById('daily-form');
    var dailyInput = document.getElementById('daily-input');
    var dailyList = document.getElementById('daily-list');
    var dailyToggle = document.getElementById('daily-toggle');
    var dailyPanel = document.getElementById('daily-panel');

    // 할일 추가
    if (form && input) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        addTodo(input.value);
        input.value = '';
        input.focus();
      });
    }

    // 할일 체크/삭제 (이벤트 위임)
    if (list) {
      list.addEventListener('click', function (e) {
        var li = e.target.closest('li');
        if (!li || li.classList.contains('empty-msg')) return;
        var id = Number(li.getAttribute('data-id'));
        if (e.target.type === 'checkbox') toggleTodo(id);
        else if (e.target.classList.contains('delete-btn')) deleteTodo(id);
      });
    }

    // 필터
    document.querySelectorAll('.filter-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        currentFilter = this.getAttribute('data-filter');
        document.querySelectorAll('.filter-btn').forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
        renderTodos();
      });
    });

    // 매일 고정 할일 토글
    if (dailyToggle && dailyPanel) {
      dailyToggle.addEventListener('click', function () {
        dailyPanel.classList.toggle('hidden');
        var icon = dailyToggle.querySelector('.daily-toggle-icon');
        if (icon) icon.textContent = dailyPanel.classList.contains('hidden') ? '\u25BE' : '\u25B4';
      });
    }

    // 매일 고정 할일 추가
    if (dailyForm && dailyInput) {
      dailyForm.addEventListener('submit', function (e) {
        e.preventDefault();
        addDailyTask(dailyInput.value);
        dailyInput.value = '';
        dailyInput.focus();
      });
    }

    // 매일 고정 할일 삭제 (이벤트 위임)
    if (dailyList) {
      dailyList.addEventListener('click', function (e) {
        if (e.target.classList.contains('delete-btn')) {
          var li = e.target.closest('li');
          if (!li) return;
          deleteDailyTask(Number(li.getAttribute('data-id')));
        }
      });
    }

    // --- 탭 전환 ---
    document.querySelectorAll('.main-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        var targetTab = this.getAttribute('data-tab');
        document.querySelectorAll('.main-tab').forEach(function (t) { t.classList.remove('active'); });
        this.classList.add('active');
        document.querySelectorAll('.tab-content').forEach(function (tc) { tc.classList.add('hidden'); });
        document.getElementById('tab-' + targetTab).classList.remove('hidden');
      });
    });

    // --- 영양제 이벤트 ---
    var suppForm = document.getElementById('supp-form');
    var suppName = document.getElementById('supp-name');
    var suppTiming = document.getElementById('supp-timing');
    var suppToggle = document.getElementById('supp-toggle');
    var suppPanel = document.getElementById('supp-panel');
    var suppList = document.getElementById('supp-list');

    // 영양제 등록
    if (suppForm && suppName && suppTiming) {
      suppForm.addEventListener('submit', function (e) {
        e.preventDefault();
        addSupplement(suppName.value, suppTiming.value);
        suppName.value = '';
        suppName.focus();
      });
    }

    // 영양제 관리 토글
    if (suppToggle && suppPanel) {
      suppToggle.addEventListener('click', function () {
        suppPanel.classList.toggle('hidden');
        var icon = suppToggle.querySelector('.daily-toggle-icon');
        if (icon) icon.textContent = suppPanel.classList.contains('hidden') ? '\u25BE' : '\u25B4';
      });
    }

    // 영양제 삭제 (이벤트 위임)
    if (suppList) {
      suppList.addEventListener('click', function (e) {
        if (e.target.classList.contains('delete-btn')) {
          var li = e.target.closest('li');
          if (!li) return;
          deleteSupplement(Number(li.getAttribute('data-id')));
        }
      });
    }
  }

  // --- Service Worker 등록 ---
  function registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js');
    }
  }

  // --- 초기화 ---
  document.addEventListener('DOMContentLoaded', function () {
    displayDate();
    dailyTasks = load(KEYS.daily, []);
    todos = load(KEYS.todos, []);
    supplements = load(KEYS.supplements, []);
    suppChecks = load(KEYS.suppChecks, {});
    checkNewDay();
    checkNewDaySupp();
    initEvents();
    updateProgress();
    renderTodos();
    renderDailyTasks();
    renderSuppChecklist();
    renderSuppList();
    updateSuppProgress();
    registerSW();
  });
})();
