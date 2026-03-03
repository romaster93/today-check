(function () {
  var KEYS = {
    todos: 'today-todos',
    daily: 'daily-tasks',
    lastDate: 'last-loaded-date'
  };

  var todos = [];
  var dailyTasks = [];
  var currentFilter = 'all';

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
      // 새로운 날: 어제 할일 초기화, 고정 할일 자동 추가
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

  // --- 렌더링 ---
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
    checkNewDay();
    initEvents();
    updateProgress();
    renderTodos();
    renderDailyTasks();
    registerSW();
  });
})();
