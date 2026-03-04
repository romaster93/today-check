#!/usr/bin/env python3
"""Today 할일 체크리스트 - 시스템 트레이 앱 (월간 플래너 + 비밀번호 + 영양제)"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AyatanaAppIndicator3, Gdk, Pango
import json
import os
import signal
import hashlib
import calendar as cal_mod
from datetime import datetime, date, timedelta

DATA_DIR = os.path.expanduser('~/.local/share/today-check')
DATA_FILE = os.path.join(DATA_DIR, 'data.json')

WIDTH_NORMAL = 420
WIDTH_WITH_CAL = 1280
WINDOW_HEIGHT = 720

SLOT_LABELS = {
    'empty': '공복',
    'morning-before': '아침 식전',
    'morning-after': '아침 식후',
    'lunch-before': '점심 식전',
    'lunch-after': '점심 식후',
    'dinner-before': '저녁 식전',
    'dinner-after': '저녁 식후',
}

SLOT_ORDER = ['empty', 'morning-before', 'morning-after', 'lunch-before', 'lunch-after', 'dinner-before', 'dinner-after']

# --- 데이터 ---

def get_today():
    return date.today().isoformat()

def format_date(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    days = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    return f"{d.year}년 {d.month}월 {d.day}일 {days[d.weekday()]}"

def hash_pw(pw):
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def load_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}
    if 'todos' in data and 'todos_by_date' not in data:
        today = get_today()
        data['todos_by_date'] = {today: data.pop('todos', [])}
        data.setdefault('daily_tasks', [])
        data['initialized_dates'] = [today]
        data.pop('last_date', None)
    data.setdefault('todos_by_date', {})
    data.setdefault('daily_tasks', [])
    data.setdefault('initialized_dates', [])
    data.setdefault('password', '')
    data.setdefault('supplements', [])
    data.setdefault('supplement_checks', {})
    return data

def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_todos_for_date(data, date_str):
    if date_str not in data.get('initialized_dates', []):
        todos = []
        for dt in data.get('daily_tasks', []):
            todos.append({'text': dt['text'], 'completed': False, 'daily': True})
        data['todos_by_date'][date_str] = todos
        data.setdefault('initialized_dates', []).append(date_str)
        save_data(data)
    else:
        todos = data['todos_by_date'].get(date_str, [])
        existing_daily = {t['text'] for t in todos if t.get('daily')}
        added = False
        for dt in data.get('daily_tasks', []):
            if dt['text'] not in existing_daily:
                todos.append({'text': dt['text'], 'completed': False, 'daily': True})
                added = True
        if added:
            data['todos_by_date'][date_str] = todos
            save_data(data)
    return data['todos_by_date'].get(date_str, [])


class PasswordDialog(Gtk.Dialog):
    def __init__(self, parent, mode='login'):
        title = '비밀번호 입력' if mode == 'login' else '비밀번호 설정'
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(300, -1)
        self.set_resizable(False)
        box = self.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(20)
        box.set_margin_bottom(12)
        box.set_margin_start(20)
        box.set_margin_end(20)
        if mode == 'login':
            box.pack_start(Gtk.Label(label='비밀번호를 입력하세요'), False, False, 0)
        else:
            box.pack_start(Gtk.Label(label='새 비밀번호를 설정하세요'), False, False, 0)
        self.pw_entry = Gtk.Entry()
        self.pw_entry.set_visibility(False)
        self.pw_entry.set_placeholder_text('비밀번호')
        self.pw_entry.connect('activate', lambda w: self.response(Gtk.ResponseType.OK))
        box.pack_start(self.pw_entry, False, False, 0)
        if mode == 'set':
            self.pw_confirm = Gtk.Entry()
            self.pw_confirm.set_visibility(False)
            self.pw_confirm.set_placeholder_text('비밀번호 확인')
            self.pw_confirm.connect('activate', lambda w: self.response(Gtk.ResponseType.OK))
            box.pack_start(self.pw_confirm, False, False, 0)
        self.error_label = Gtk.Label()
        box.pack_start(self.error_label, False, False, 0)
        btn_box = Gtk.Box(spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        if mode != 'login':
            c = Gtk.Button(label='취소')
            c.connect('clicked', lambda w: self.response(Gtk.ResponseType.CANCEL))
            btn_box.pack_start(c, False, False, 0)
        o = Gtk.Button(label='확인')
        o.connect('clicked', lambda w: self.response(Gtk.ResponseType.OK))
        btn_box.pack_start(o, False, False, 0)
        box.pack_start(btn_box, False, False, 0)
        self.show_all()

    def get_password(self):
        return self.pw_entry.get_text()

    def get_confirm(self):
        return self.pw_confirm.get_text() if hasattr(self, 'pw_confirm') else ''

    def set_error(self, msg):
        self.error_label.set_markup(f'<span foreground="#e74c3c">{msg}</span>')


class TodoTrayApp:
    def __init__(self):
        self.data = load_data()
        self.selected_date = get_today()
        self.cal_visible = False
        self.supp_visible = False
        self.supp_filter = 'all'
        self.supp_filter_btns = {}
        self.cal_year = date.today().year
        self.cal_month = date.today().month
        get_todos_for_date(self.data, self.selected_date)

        self.window = None
        self.cal_panel = None
        self.cal_grid = None
        self.cal_month_label = None
        self.date_label = None
        self.todo_box = None
        self.daily_box = None
        self.progress_label = None
        self.progress_bar = None
        self.input_entry = None
        self.todo_container = None
        self.supp_container = None
        self.supp_check_box = None
        self.supp_list_box = None
        self.supp_progress_label = None
        self.supp_progress_bar = None
        self.supp_name_entry = None
        self.supp_slot_combo = None
        self.supp_toggle_btn = None
        self.supp_missed_card = None
        self.supp_missed_box = None

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.svg')
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            'today-check', icon_path,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.update_indicator_label()
        self.build_tray_menu()
        self.build_window()
        GLib.timeout_add_seconds(60, self.periodic_check)

    def get_current_todos(self):
        return self.data['todos_by_date'].get(self.selected_date, [])

    def get_today_todos(self):
        return self.data['todos_by_date'].get(get_today(), [])

    def update_indicator_label(self):
        todos = self.get_today_todos()
        done = sum(1 for t in todos if t['completed'])
        supps = self.data.get('supplements', [])
        checks = self.data['supplement_checks'].get(get_today(), [])
        supp_done = sum(1 for s in supps if s['id'] in checks)
        if supps:
            self.indicator.set_label(f' \u2713{done}/{len(todos)}  \U0001F48A{supp_done}/{len(supps)}', '')
        else:
            self.indicator.set_label(f' {done}/{len(todos)}', '')

    # --- 트레이 메뉴 ---

    def build_tray_menu(self):
        menu = Gtk.Menu()
        header = Gtk.MenuItem(label=format_date(get_today()))
        header.set_sensitive(False)
        menu.append(header)
        menu.append(Gtk.SeparatorMenuItem())

        today_todos = self.get_today_todos()
        if not today_todos:
            e = Gtk.MenuItem(label='  할일이 없습니다')
            e.set_sensitive(False)
            menu.append(e)
        else:
            for i, todo in enumerate(today_todos):
                ck = '\u2713' if todo['completed'] else '\u25CB'
                txt = todo['text'] + (' [매일]' if todo.get('daily') else '')
                item = Gtk.MenuItem(label=f'  {ck}  {txt}')
                item.connect('activate', self.on_tray_toggle, i)
                menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())
        done = sum(1 for t in today_todos if t['completed'])
        p = Gtk.MenuItem(label=f'  완료: {done}/{len(today_todos)}')
        p.set_sensitive(False)
        menu.append(p)
        menu.append(Gtk.SeparatorMenuItem())

        # 영양제 섹션
        supplements = self.data.get('supplements', [])
        if supplements:
            menu.append(Gtk.SeparatorMenuItem())
            today_checks = self.data['supplement_checks'].get(get_today(), [])
            supp_done = sum(1 for s in supplements if s['id'] in today_checks)
            sh = Gtk.MenuItem(label=f'  \U0001F48A 복용: {supp_done}/{len(supplements)}')
            sh.set_sensitive(False)
            menu.append(sh)
            sorted_supps = sorted(supplements, key=lambda s: SLOT_ORDER.index(s['slot']) if s['slot'] in SLOT_ORDER else 99)
            for supp in sorted_supps:
                ck = '\u2713' if supp['id'] in today_checks else '\u25CB'
                slot_label = SLOT_LABELS.get(supp['slot'], '')
                item = Gtk.MenuItem(label=f'  {ck}  {supp["name"]}  ({slot_label})')
                item.connect('activate', self.on_tray_supp_toggle, supp['id'])
                menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())
        for label, cb in [('열기', self.on_open_window), ('비밀번호 설정', self.on_change_password), ('종료', self.on_quit)]:
            item = Gtk.MenuItem(label=label)
            item.connect('activate', cb)
            menu.append(item)

        menu.show_all()
        self.indicator.set_menu(menu)

    def on_tray_toggle(self, widget, idx):
        today = get_today()
        todos = self.data['todos_by_date'].get(today, [])
        if 0 <= idx < len(todos):
            todos[idx]['completed'] = not todos[idx]['completed']
            save_data(self.data)
            self.update_indicator_label()
            self.build_tray_menu()
            if self.selected_date == today and self.window and self.window.get_visible():
                self.refresh_todo_list()

    # --- 메인 윈도우 ---

    def build_window(self):
        self.window = Gtk.Window(title='오늘의 할일 체크리스트')
        self.window.set_default_size(WIDTH_NORMAL, WINDOW_HEIGHT)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        icon_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon-48.png')
        if os.path.exists(icon_file):
            self.window.set_icon_from_file(icon_file)
        else:
            self.window.set_icon_name('task-due')
        self.window.connect('delete-event', self.on_window_close)

        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window { background: #1a1a2e; }
            .card { background: #252542; border-radius: 12px; padding: 20px; }
            .header-label { font-size: 18px; font-weight: bold; color: #e8e8e8; }
            .todo-text { font-size: 14px; color: #ddd; }
            .daily-badge { font-size: 11px; color: #6a8cff; }
            .delete-btn { color: #555; font-size: 14px; }
            .delete-btn:hover { color: #e74c3c; }
            .edit-btn { color: #555; font-size: 14px; }
            .edit-btn:hover { color: #4a6cf7; }
            .section-title { font-size: 13px; font-weight: bold; color: #aaa; }
            .hint-label { font-size: 11px; color: #666; }
            .progress-text { font-size: 13px; color: #888; }
            .cal-toggle { background: #3a3a5c; color: #aaa; border-radius: 8px; padding: 6px 14px; font-size: 13px; }
            .cal-toggle:hover { background: #4a6cf7; color: white; }
            .today-btn { background: #4a6cf7; color: white; border-radius: 8px; padding: 4px 12px; font-size: 12px; }
            .cal-nav-btn { background: #3a3a5c; color: #ddd; border-radius: 6px; padding: 4px 10px; }
            .cal-nav-btn:hover { background: #4a6cf7; }
            .cal-month-label { font-size: 15px; font-weight: bold; color: #e8e8e8; }
            entry { border-radius: 8px; padding: 8px; background: #1e1e36; color: #ddd; border: 1px solid #3a3a5c; }
            button.add-btn { background: #4a6cf7; color: white; border-radius: 8px; padding: 8px 16px; }
            button.daily-add-btn { background: #555; color: white; border-radius: 8px; padding: 8px 16px; }
            checkbutton { color: #ddd; }
            label { color: #ddd; }
            separator { background: #3a3a5c; }
            .cal-day-header { font-size: 11px; font-weight: bold; color: #888; padding: 4px; }
            .cal-cell { background: #1e1e36; border-radius: 6px; padding: 4px; min-height: 100px; }
            .cal-cell:hover { background: #2a2a4a; }
            .cal-cell-today { background: #1e2e4e; border: 1px solid #4a6cf7; }
            .cal-cell-selected { background: #2a3a6e; border: 1px solid #6a8cff; }
            .cal-cell-other { background: #16162a; }
            .cal-date-num { font-size: 14px; font-weight: bold; color: #aaa; }
            .cal-date-today { color: #4a6cf7; }
            .cal-date-selected { color: #6a8cff; }
            .cal-date-other { color: #444; }
            .cal-todo-preview { font-size: 11px; color: #888; }
            .cal-todo-done { font-size: 11px; color: #555; }
            .cal-cell-sun .cal-date-num { color: #e74c3c; }
            .cal-cell-sat .cal-date-num { color: #4a90d9; }
            .overdue-date-label { font-size: 13px; font-weight: bold; color: #e8a838; margin-top: 4px; }
            .overdue-badge { font-size: 11px; color: #e8a838; }
            .add-today-btn { color: #6a8cff; font-size: 12px; }
            .add-today-btn:hover { color: #4a6cf7; }
            .supp-toggle-active { background: #10b981; color: white; border-radius: 8px; padding: 6px 14px; font-size: 13px; }
            .supp-group-header { font-size: 13px; font-weight: bold; color: #34d399; }
            .supp-slot-badge { font-size: 11px; color: #10b981; }
            button.supp-add-btn { background: #10b981; color: white; border-radius: 8px; padding: 8px 16px; }
            button.supp-add-btn:hover { background: #059669; }
            .supp-progress-text { font-size: 13px; color: #10b981; }
            combobox button { background: #1e1e36; color: #ddd; border: 1px solid #3a3a5c; border-radius: 8px; padding: 6px 10px; }
            .supp-filter-btn { background: #3a3a5c; color: #aaa; border-radius: 8px; padding: 4px 8px; font-size: 12px; }
            .supp-filter-btn:hover { background: #2a4a3a; color: #ddd; }
            .supp-filter-btn-active { background: #10b981; color: white; border-radius: 8px; padding: 4px 8px; font-size: 12px; }
            .supp-missed-title { font-size: 13px; font-weight: bold; color: #e8a838; }
            .supp-missed-msg { font-size: 12px; color: #e8a838; }
            .supp-taken-btn { color: #10b981; font-size: 12px; }
            .supp-taken-btn:hover { color: #059669; }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # === 왼쪽 패널 ===
        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left_scroll.set_size_request(WIDTH_NORMAL, -1)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        left_box.set_margin_top(20)
        left_box.set_margin_bottom(20)
        left_box.set_margin_start(20)
        left_box.set_margin_end(20)

        # 헤더 카드 (항상 표시)
        header_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        header_card.get_style_context().add_class('card')

        header_row = Gtk.Box(spacing=8)
        self.date_label = Gtk.Label()
        self.date_label.get_style_context().add_class('header-label')
        self.date_label.set_halign(Gtk.Align.START)
        header_row.pack_start(self.date_label, True, True, 0)

        self.supp_toggle_btn = Gtk.Button(label='\U0001F48A 영양제')
        self.supp_toggle_btn.get_style_context().add_class('cal-toggle')
        self.supp_toggle_btn.connect('clicked', self.on_toggle_supplement_view)
        header_row.pack_start(self.supp_toggle_btn, False, False, 0)

        self.cal_toggle_btn = Gtk.Button(label='\U0001F4C5 달력')
        self.cal_toggle_btn.get_style_context().add_class('cal-toggle')
        self.cal_toggle_btn.connect('clicked', self.on_toggle_calendar)
        header_row.pack_start(self.cal_toggle_btn, False, False, 0)

        header_card.pack_start(header_row, False, False, 0)
        left_box.pack_start(header_card, False, False, 0)

        # === 할일 컨테이너 ===
        self.todo_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.todo_container.set_hexpand(True)

        # 할일 카드
        todo_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        todo_card.get_style_context().add_class('card')

        input_box = Gtk.Box(spacing=8)
        self.input_entry = Gtk.Entry()
        self.input_entry.set_placeholder_text('할일을 입력하세요...')
        self.input_entry.connect('activate', self.on_add_todo)
        self.input_entry.connect('key-press-event', self.on_entry_key_press)
        input_box.pack_start(self.input_entry, True, True, 0)
        add_btn = Gtk.Button(label='추가')
        add_btn.get_style_context().add_class('add-btn')
        add_btn.connect('clicked', self.on_add_todo)
        input_box.pack_start(add_btn, False, False, 0)
        todo_card.pack_start(input_box, False, False, 4)

        self.todo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        todo_card.pack_start(self.todo_box, False, False, 0)

        todo_card.pack_start(Gtk.Separator(), False, False, 4)
        self.progress_label = Gtk.Label()
        self.progress_label.get_style_context().add_class('progress-text')
        todo_card.pack_start(self.progress_label, False, False, 0)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_size_request(-1, 8)
        todo_card.pack_start(self.progress_bar, False, False, 0)

        self.todo_container.pack_start(todo_card, False, False, 0)

        # 매일 고정 할일 카드
        daily_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        daily_card.get_style_context().add_class('card')
        dt = Gtk.Label(label='매일 고정 할일 관리')
        dt.get_style_context().add_class('section-title')
        dt.set_halign(Gtk.Align.START)
        daily_card.pack_start(dt, False, False, 0)

        di_box = Gtk.Box(spacing=8)
        self.daily_entry = Gtk.Entry()
        self.daily_entry.set_placeholder_text('매일 반복할 할일...')
        self.daily_entry.connect('activate', self.on_add_daily)
        self.daily_entry.connect('key-press-event', self.on_entry_key_press)
        di_box.pack_start(self.daily_entry, True, True, 0)
        dab = Gtk.Button(label='등록')
        dab.get_style_context().add_class('daily-add-btn')
        dab.connect('clicked', self.on_add_daily)
        di_box.pack_start(dab, False, False, 0)
        daily_card.pack_start(di_box, False, False, 0)

        self.daily_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        daily_card.pack_start(self.daily_box, False, False, 0)
        hint = Gtk.Label(label='여기 등록된 할일은 매일 자동으로 체크리스트에 추가됩니다.')
        hint.get_style_context().add_class('hint-label')
        daily_card.pack_start(hint, False, False, 4)

        self.todo_container.pack_start(daily_card, False, False, 0)

        # 아직 못한 일 카드
        overdue_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        overdue_card.get_style_context().add_class('card')
        ot = Gtk.Label(label='아직 못한 일')
        ot.get_style_context().add_class('section-title')
        ot.set_halign(Gtk.Align.START)
        overdue_card.pack_start(ot, False, False, 0)
        self.overdue_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        overdue_card.pack_start(self.overdue_box, False, False, 0)
        overdue_hint = Gtk.Label(label='최근 2일간 완료하지 못한 할일이 표시됩니다.')
        overdue_hint.get_style_context().add_class('hint-label')
        overdue_card.pack_start(overdue_hint, False, False, 4)
        self.todo_container.pack_start(overdue_card, False, False, 0)

        left_box.pack_start(self.todo_container, False, False, 0)

        # === 영양제 컨테이너 (기본 숨김) ===
        self.supp_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.supp_container.set_hexpand(True)

        # 영양제 체크리스트 카드
        supp_check_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        supp_check_card.get_style_context().add_class('card')

        supp_filter_box = Gtk.Box(spacing=6)
        supp_filter_box.set_halign(Gtk.Align.CENTER)
        for label, fval in [('전체', 'all'), ('공복', 'empty'), ('아침', 'morning'), ('점심', 'lunch'), ('저녁', 'dinner')]:
            btn = Gtk.Button(label=label)
            if fval == 'all':
                btn.get_style_context().add_class('supp-filter-btn-active')
            else:
                btn.get_style_context().add_class('supp-filter-btn')
            btn.connect('clicked', self.on_supp_filter, fval)
            supp_filter_box.pack_start(btn, True, True, 0)
            self.supp_filter_btns[fval] = btn
        supp_check_card.pack_start(supp_filter_box, False, False, 4)

        self.supp_check_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        supp_check_card.pack_start(self.supp_check_box, False, False, 0)

        supp_check_card.pack_start(Gtk.Separator(), False, False, 4)
        self.supp_progress_label = Gtk.Label()
        self.supp_progress_label.get_style_context().add_class('supp-progress-text')
        supp_check_card.pack_start(self.supp_progress_label, False, False, 0)
        self.supp_progress_bar = Gtk.ProgressBar()
        self.supp_progress_bar.set_size_request(-1, 8)
        supp_check_card.pack_start(self.supp_progress_bar, False, False, 0)

        self.supp_container.pack_start(supp_check_card, False, False, 0)

        # 어제 안 드신 영양제 카드
        self.supp_missed_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.supp_missed_card.get_style_context().add_class('card')
        self.supp_missed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.supp_missed_card.pack_start(self.supp_missed_box, False, False, 0)
        self.supp_container.pack_start(self.supp_missed_card, False, False, 0)

        # 영양제 관리 카드
        supp_manage_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        supp_manage_card.get_style_context().add_class('card')
        st = Gtk.Label(label='영양제 관리')
        st.get_style_context().add_class('section-title')
        st.set_halign(Gtk.Align.START)
        supp_manage_card.pack_start(st, False, False, 0)

        si_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        si_row1 = Gtk.Box(spacing=8)
        self.supp_name_entry = Gtk.Entry()
        self.supp_name_entry.set_placeholder_text('영양제 이름...')
        self.supp_name_entry.connect('activate', self.on_add_supplement)
        self.supp_name_entry.connect('key-press-event', self.on_entry_key_press)
        si_row1.pack_start(self.supp_name_entry, True, True, 0)
        sab = Gtk.Button(label='등록')
        sab.get_style_context().add_class('supp-add-btn')
        sab.connect('clicked', self.on_add_supplement)
        si_row1.pack_start(sab, False, False, 0)
        si_box.pack_start(si_row1, False, False, 0)

        si_row2 = Gtk.Box(spacing=8)
        self.supp_slot_combo = Gtk.ComboBoxText()
        for slot in SLOT_ORDER:
            self.supp_slot_combo.append(slot, SLOT_LABELS[slot])
        self.supp_slot_combo.set_active_id('morning-after')
        si_row2.pack_start(self.supp_slot_combo, True, True, 0)
        si_box.pack_start(si_row2, False, False, 0)

        supp_manage_card.pack_start(si_box, False, False, 0)

        self.supp_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        supp_manage_card.pack_start(self.supp_list_box, False, False, 0)
        supp_hint = Gtk.Label(label='등록된 영양제는 매일 체크리스트에 표시됩니다.')
        supp_hint.get_style_context().add_class('hint-label')
        supp_manage_card.pack_start(supp_hint, False, False, 4)

        self.supp_container.pack_start(supp_manage_card, False, False, 0)

        self.supp_container.set_no_show_all(True)
        self.supp_container.hide()
        left_box.pack_start(self.supp_container, False, False, 0)

        left_scroll.add(left_box)
        hbox.pack_start(left_scroll, False, False, 0)

        # === 오른쪽: 월간 플래너 달력 ===
        self.cal_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.cal_panel.set_margin_top(20)
        self.cal_panel.set_margin_bottom(20)
        self.cal_panel.set_margin_start(4)
        self.cal_panel.set_margin_end(20)
        self.cal_panel.set_size_request(830, -1)

        cal_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cal_card.get_style_context().add_class('card')

        # 월 네비게이션
        nav = Gtk.Box(spacing=12)
        nav.set_halign(Gtk.Align.CENTER)
        prev_btn = Gtk.Button(label='\u25C0')
        prev_btn.get_style_context().add_class('cal-nav-btn')
        prev_btn.connect('clicked', self.on_prev_month)
        nav.pack_start(prev_btn, False, False, 0)

        self.cal_month_label = Gtk.Label()
        self.cal_month_label.get_style_context().add_class('cal-month-label')
        nav.pack_start(self.cal_month_label, False, False, 8)

        next_btn = Gtk.Button(label='\u25B6')
        next_btn.get_style_context().add_class('cal-nav-btn')
        next_btn.connect('clicked', self.on_next_month)
        nav.pack_start(next_btn, False, False, 0)

        today_btn = Gtk.Button(label='오늘')
        today_btn.get_style_context().add_class('today-btn')
        today_btn.connect('clicked', self.on_go_today)
        nav.pack_start(today_btn, False, False, 8)

        cal_card.pack_start(nav, False, False, 4)

        # 달력 그리드 컨테이너
        self.cal_grid_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        cal_card.pack_start(self.cal_grid_container, True, True, 0)

        self.cal_panel.pack_start(cal_card, True, True, 0)
        self.cal_panel.set_no_show_all(True)
        self.cal_panel.hide()

        hbox.pack_start(self.cal_panel, True, True, 0)
        self.window.add(hbox)

        self.refresh_todo_list()
        self.refresh_daily_list()
        self.refresh_supp_checklist()
        self.refresh_supp_list()
        self.refresh_supp_missed()

    # --- 월간 플래너 달력 ---

    def build_calendar_grid(self):
        for child in self.cal_grid_container.get_children():
            self.cal_grid_container.remove(child)

        self.cal_month_label.set_text(f'{self.cal_year}년 {self.cal_month}월')

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_row_spacing(4)
        grid.set_column_spacing(4)

        day_names = ['월', '화', '수', '목', '금', '토', '일']
        for col, name in enumerate(day_names):
            lbl = Gtk.Label(label=name)
            lbl.get_style_context().add_class('cal-day-header')
            if col == 6:
                lbl.set_markup(f'<span foreground="#e74c3c">{name}</span>')
            elif col == 5:
                lbl.set_markup(f'<span foreground="#4a90d9">{name}</span>')
            grid.attach(lbl, col, 0, 1, 1)

        first_weekday, days_in_month = cal_mod.monthrange(self.cal_year, self.cal_month)
        today_str = get_today()

        if self.cal_month == 1:
            prev_year, prev_month = self.cal_year - 1, 12
        else:
            prev_year, prev_month = self.cal_year, self.cal_month - 1
        _, prev_days = cal_mod.monthrange(prev_year, prev_month)

        cells = []
        for i in range(first_weekday):
            d = prev_days - first_weekday + 1 + i
            ds = f'{prev_year}-{prev_month:02d}-{d:02d}'
            cells.append((d, ds, 'other'))
        for d in range(1, days_in_month + 1):
            ds = f'{self.cal_year}-{self.cal_month:02d}-{d:02d}'
            cells.append((d, ds, 'current'))
        remaining = 7 - (len(cells) % 7)
        if remaining < 7:
            if self.cal_month == 12:
                nx_year, nx_month = self.cal_year + 1, 1
            else:
                nx_year, nx_month = self.cal_year, self.cal_month + 1
            for d in range(1, remaining + 1):
                ds = f'{nx_year}-{nx_month:02d}-{d:02d}'
                cells.append((d, ds, 'other'))

        for idx, (day_num, date_str, kind) in enumerate(cells):
            col = idx % 7
            row = idx // 7 + 1

            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            cell.get_style_context().add_class('cal-cell')

            if kind == 'other':
                cell.get_style_context().add_class('cal-cell-other')
            if date_str == today_str:
                cell.get_style_context().add_class('cal-cell-today')
            if date_str == self.selected_date:
                cell.get_style_context().add_class('cal-cell-selected')
            if col == 6:
                cell.get_style_context().add_class('cal-cell-sun')
            elif col == 5:
                cell.get_style_context().add_class('cal-cell-sat')

            num_lbl = Gtk.Label(label=str(day_num))
            num_lbl.set_halign(Gtk.Align.START)
            num_lbl.get_style_context().add_class('cal-date-num')
            if kind == 'other':
                num_lbl.get_style_context().add_class('cal-date-other')
            elif date_str == today_str:
                num_lbl.get_style_context().add_class('cal-date-today')
            elif date_str == self.selected_date:
                num_lbl.get_style_context().add_class('cal-date-selected')
            cell.pack_start(num_lbl, False, False, 0)

            if self.supp_visible:
                supplements = self.data.get('supplements', [])
                checks = self.data['supplement_checks'].get(date_str, [])
                sorted_supps = sorted(supplements, key=lambda s: SLOT_ORDER.index(s['slot']) if s['slot'] in SLOT_ORDER else 99)
                for supp in sorted_supps[:4]:
                    text = supp['name']
                    preview = Gtk.Label(label=text)
                    preview.set_halign(Gtk.Align.START)
                    preview.set_ellipsize(Pango.EllipsizeMode.END)
                    preview.set_max_width_chars(24)
                    if supp['id'] in checks:
                        preview.get_style_context().add_class('cal-todo-done')
                        esc = GLib.markup_escape_text(text)
                        preview.set_markup(f'<s><span foreground="#555">{esc}</span></s>')
                    else:
                        preview.get_style_context().add_class('cal-todo-preview')
                    cell.pack_start(preview, False, False, 0)
                if len(sorted_supps) > 4:
                    more = Gtk.Label(label=f'+{len(sorted_supps)-4}개 더')
                    more.set_halign(Gtk.Align.START)
                    more.get_style_context().add_class('hint-label')
                    cell.pack_start(more, False, False, 0)
            else:
                todos = self.data['todos_by_date'].get(date_str, [])
                for t in todos[:4]:
                    text = t['text']
                    preview = Gtk.Label(label=text)
                    preview.set_halign(Gtk.Align.START)
                    preview.set_ellipsize(Pango.EllipsizeMode.END)
                    preview.set_max_width_chars(24)
                    if t['completed']:
                        preview.get_style_context().add_class('cal-todo-done')
                        esc = GLib.markup_escape_text(text)
                        preview.set_markup(f'<s><span foreground="#555">{esc}</span></s>')
                    else:
                        preview.get_style_context().add_class('cal-todo-preview')
                    cell.pack_start(preview, False, False, 0)
                if len(todos) > 4:
                    more = Gtk.Label(label=f'+{len(todos)-4}개 더')
                    more.set_halign(Gtk.Align.START)
                    more.get_style_context().add_class('hint-label')
                    cell.pack_start(more, False, False, 0)

            event_box = Gtk.EventBox()
            event_box.add(cell)
            event_box.connect('button-press-event', self.on_cal_cell_click, date_str)
            grid.attach(event_box, col, row, 1, 1)

        self.cal_grid_container.pack_start(grid, True, True, 0)
        self.cal_grid_container.show_all()

    def on_cal_cell_click(self, widget, event, date_str):
        self.selected_date = date_str
        get_todos_for_date(self.data, date_str)
        self.refresh_todo_list()
        self.build_calendar_grid()

    def on_prev_month(self, widget):
        if self.cal_month == 1:
            self.cal_year -= 1
            self.cal_month = 12
        else:
            self.cal_month -= 1
        self.build_calendar_grid()

    def on_next_month(self, widget):
        if self.cal_month == 12:
            self.cal_year += 1
            self.cal_month = 1
        else:
            self.cal_month += 1
        self.build_calendar_grid()

    def on_go_today(self, widget):
        t = date.today()
        self.cal_year = t.year
        self.cal_month = t.month
        self.selected_date = t.isoformat()
        get_todos_for_date(self.data, self.selected_date)
        self.refresh_todo_list()
        self.build_calendar_grid()

    # --- 달력 토글 ---

    def on_toggle_calendar(self, widget):
        self.cal_visible = not self.cal_visible
        if self.cal_visible:
            self.cal_panel.set_no_show_all(False)
            self.cal_panel.show_all()
            self.window.resize(WIDTH_WITH_CAL, WINDOW_HEIGHT)
            self.build_calendar_grid()
        else:
            self.cal_panel.hide()
            self.cal_panel.set_no_show_all(True)
            self.window.resize(WIDTH_NORMAL, WINDOW_HEIGHT)

    # --- 영양제 뷰 토글 ---

    def on_toggle_supplement_view(self, widget):
        self.supp_visible = not self.supp_visible
        if self.supp_visible:
            self.todo_container.hide()
            self.todo_container.set_no_show_all(True)
            self.supp_container.set_no_show_all(False)
            self.supp_container.show_all()
            self.supp_toggle_btn.get_style_context().remove_class('cal-toggle')
            self.supp_toggle_btn.get_style_context().add_class('supp-toggle-active')
            self.refresh_supp_checklist()
            self.refresh_supp_list()
            self.refresh_supp_missed()
        else:
            self.supp_container.hide()
            self.supp_container.set_no_show_all(True)
            self.todo_container.set_no_show_all(False)
            self.todo_container.show_all()
            self.supp_toggle_btn.get_style_context().remove_class('supp-toggle-active')
            self.supp_toggle_btn.get_style_context().add_class('cal-toggle')
        if self.cal_visible:
            self.build_calendar_grid()
        target_w = WIDTH_WITH_CAL if self.cal_visible else WIDTH_NORMAL
        GLib.idle_add(self.window.resize, target_w, WINDOW_HEIGHT)

    # --- 비밀번호 ---

    def check_password(self):
        if not self.data.get('password'):
            return True
        while True:
            dlg = PasswordDialog(self.window, mode='login')
            resp = dlg.run()
            if resp == Gtk.ResponseType.OK:
                if hash_pw(dlg.get_password()) == self.data['password']:
                    dlg.destroy()
                    return True
                dlg.set_error('비밀번호가 틀렸습니다.')
                dlg.destroy()
            else:
                dlg.destroy()
                return False

    def on_change_password(self, widget=None):
        if self.data.get('password'):
            dlg = PasswordDialog(self.window, mode='login')
            resp = dlg.run()
            ok = resp == Gtk.ResponseType.OK and hash_pw(dlg.get_password()) == self.data['password']
            dlg.destroy()
            if not ok:
                return
        dlg = PasswordDialog(self.window, mode='set')
        while True:
            resp = dlg.run()
            if resp != Gtk.ResponseType.OK:
                dlg.destroy()
                return
            pw, confirm = dlg.get_password(), dlg.get_confirm()
            if not pw:
                self.data['password'] = ''
                save_data(self.data)
                dlg.destroy()
                return
            if pw != confirm:
                dlg.set_error('비밀번호가 일치하지 않습니다.')
                continue
            self.data['password'] = hash_pw(pw)
            save_data(self.data)
            dlg.destroy()
            return

    # --- 미완료 할일 ---

    def get_overdue_todos(self):
        today = date.today()
        result = []
        for days_ago in [1, 2]:
            d = today - timedelta(days=days_ago)
            date_str = d.isoformat()
            todos = self.data['todos_by_date'].get(date_str, [])
            for idx, todo in enumerate(todos):
                if not todo['completed']:
                    result.append((date_str, idx, todo))
        return result

    def refresh_overdue_list(self):
        for child in self.overdue_box.get_children():
            self.overdue_box.remove(child)

        overdue = self.get_overdue_todos()
        if not overdue:
            empty = Gtk.Label(label='최근 미완료 할일이 없습니다')
            empty.get_style_context().add_class('hint-label')
            empty.set_margin_top(8)
            empty.set_margin_bottom(8)
            self.overdue_box.pack_start(empty, False, False, 0)
        else:
            grouped = {}
            for date_str, idx, todo in overdue:
                grouped.setdefault(date_str, []).append((idx, todo))
            for date_str in sorted(grouped.keys(), reverse=True):
                d = date.fromisoformat(date_str)
                days_kr = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
                date_lbl = Gtk.Label(label=f'{d.month}월 {d.day}일 {days_kr[d.weekday()]}')
                date_lbl.get_style_context().add_class('overdue-date-label')
                date_lbl.set_halign(Gtk.Align.START)
                self.overdue_box.pack_start(date_lbl, False, False, 2)

                for idx, todo in grouped[date_str]:
                    row = Gtk.Box(spacing=6)
                    row.set_margin_top(2)
                    row.set_margin_bottom(2)
                    check = Gtk.CheckButton()
                    check.set_active(False)
                    check.connect('toggled', self.on_toggle_overdue, date_str, idx)
                    row.pack_start(check, False, False, 0)
                    label = Gtk.Label(label=todo['text'])
                    label.set_halign(Gtk.Align.START)
                    label.set_hexpand(True)
                    label.set_line_wrap(True)
                    label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                    label.set_size_request(260, -1)
                    label.get_style_context().add_class('todo-text')
                    row.pack_start(label, True, True, 0)
                    if todo.get('daily'):
                        badge = Gtk.Label(label='매일')
                        badge.get_style_context().add_class('overdue-badge')
                        row.pack_start(badge, False, False, 0)
                    add_btn = Gtk.Button(label='오늘 추가')
                    add_btn.get_style_context().add_class('add-today-btn')
                    add_btn.set_relief(Gtk.ReliefStyle.NONE)
                    add_btn.set_tooltip_text('오늘 할일로 추가')
                    add_btn.connect('clicked', self.on_add_overdue_to_today, date_str, idx)
                    row.pack_start(add_btn, False, False, 0)
                    self.overdue_box.pack_start(row, False, False, 0)

        self.overdue_box.show_all()

    def on_add_overdue_to_today(self, widget, date_str, idx):
        todos = self.data['todos_by_date'].get(date_str, [])
        if 0 <= idx < len(todos):
            todo = todos[idx]
            today = get_today()
            today_todos = self.data['todos_by_date'].setdefault(today, [])
            if any(t['text'] == todo['text'] for t in today_todos):
                return
            today_todos.append({'text': todo['text'], 'completed': False, 'daily': False})
            todo['completed'] = True
            save_data(self.data)
            self.refresh_todo_list()
            self.update_indicator_label()
            self.build_tray_menu()
            if self.cal_visible:
                self.build_calendar_grid()

    def on_toggle_overdue(self, widget, date_str, idx):
        todos = self.data['todos_by_date'].get(date_str, [])
        if 0 <= idx < len(todos):
            todos[idx]['completed'] = True
            save_data(self.data)
            self.refresh_overdue_list()
            self.update_indicator_label()
            self.build_tray_menu()
            if self.cal_visible:
                self.build_calendar_grid()

    # --- 새로고침 ---

    def refresh_todo_list(self):
        for child in self.todo_box.get_children():
            self.todo_box.remove(child)

        self.date_label.set_text(format_date(self.selected_date))
        todos = self.get_current_todos()

        if not todos:
            empty = Gtk.Label(label='할일을 추가해보세요!')
            empty.get_style_context().add_class('hint-label')
            empty.set_margin_top(16)
            empty.set_margin_bottom(16)
            self.todo_box.pack_start(empty, False, False, 0)
        else:
            for i, todo in enumerate(todos):
                row = Gtk.Box(spacing=6)
                row.set_margin_top(4)
                row.set_margin_bottom(4)

                check = Gtk.CheckButton()
                check.set_active(todo['completed'])
                check.connect('toggled', self.on_toggle_todo, i)
                row.pack_start(check, False, False, 0)

                label = Gtk.Label(label=todo['text'])
                label.set_halign(Gtk.Align.START)
                label.set_hexpand(True)
                label.set_line_wrap(True)
                label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                label.set_size_request(260, -1)
                label.get_style_context().add_class('todo-text')
                if todo['completed']:
                    label.set_markup(f'<s><span foreground="#666">{GLib.markup_escape_text(todo["text"])}</span></s>')
                row.pack_start(label, True, True, 0)

                if todo.get('daily'):
                    badge = Gtk.Label(label='매일')
                    badge.get_style_context().add_class('daily-badge')
                    row.pack_start(badge, False, False, 0)

                edit_btn = Gtk.Button(label='\u270E')
                edit_btn.get_style_context().add_class('edit-btn')
                edit_btn.set_relief(Gtk.ReliefStyle.NONE)
                edit_btn.set_tooltip_text('수정')
                edit_btn.connect('clicked', self.on_edit_todo, i)
                row.pack_start(edit_btn, False, False, 0)

                del_btn = Gtk.Button(label='\u2715')
                del_btn.get_style_context().add_class('delete-btn')
                del_btn.set_relief(Gtk.ReliefStyle.NONE)
                del_btn.set_tooltip_text('삭제')
                del_btn.connect('clicked', self.on_delete_todo, i)
                row.pack_start(del_btn, False, False, 0)

                self.todo_box.pack_start(row, False, False, 0)

        total = len(todos)
        done = sum(1 for t in todos if t['completed'])
        self.progress_label.set_text(f'완료: {done}/{total}')
        self.progress_bar.set_fraction(done / total if total > 0 else 0)
        self.todo_box.show_all()
        self.refresh_overdue_list()

    def refresh_daily_list(self):
        for child in self.daily_box.get_children():
            self.daily_box.remove(child)
        if not self.data['daily_tasks']:
            e = Gtk.Label(label='등록된 고정 할일이 없습니다.')
            e.get_style_context().add_class('hint-label')
            e.set_margin_top(8)
            e.set_margin_bottom(8)
            self.daily_box.pack_start(e, False, False, 0)
        else:
            for i, dt in enumerate(self.data['daily_tasks']):
                row = Gtk.Box(spacing=8)
                row.set_margin_top(2)
                row.set_margin_bottom(2)
                lbl = Gtk.Label(label=dt['text'])
                lbl.set_halign(Gtk.Align.START)
                lbl.set_hexpand(True)
                row.pack_start(lbl, True, True, 0)
                db = Gtk.Button(label='\u2715')
                db.get_style_context().add_class('delete-btn')
                db.set_relief(Gtk.ReliefStyle.NONE)
                db.connect('clicked', self.on_delete_daily, i)
                row.pack_start(db, False, False, 0)
                self.daily_box.pack_start(row, False, False, 0)
        self.daily_box.show_all()

    # --- 영양제 ---

    def get_today_supp_checks(self):
        return self.data['supplement_checks'].get(get_today(), [])

    def refresh_supp_checklist(self):
        for child in self.supp_check_box.get_children():
            self.supp_check_box.remove(child)

        all_supplements = self.data.get('supplements', [])
        if self.supp_filter != 'all':
            supplements = [s for s in all_supplements if s['slot'].startswith(self.supp_filter)]
        else:
            supplements = all_supplements
        if not supplements:
            empty = Gtk.Label(label='아래 영양제 관리에서 등록해보세요!' if not all_supplements else '해당 시간대 영양제가 없습니다.')
            empty.get_style_context().add_class('hint-label')
            empty.set_margin_top(16)
            empty.set_margin_bottom(16)
            self.supp_check_box.pack_start(empty, False, False, 0)
        else:
            groups = {}
            for supp in supplements:
                groups.setdefault(supp['slot'], []).append(supp)

            today_checks = self.get_today_supp_checks()

            for slot in SLOT_ORDER:
                if slot not in groups:
                    continue
                header = Gtk.Label()
                header.set_markup(f'<b>{SLOT_LABELS[slot]}</b>')
                header.get_style_context().add_class('supp-group-header')
                header.set_halign(Gtk.Align.START)
                header.set_margin_top(6)
                self.supp_check_box.pack_start(header, False, False, 0)

                for supp in groups[slot]:
                    row = Gtk.Box(spacing=8)
                    row.set_margin_top(2)
                    row.set_margin_bottom(2)
                    row.set_margin_start(8)

                    is_checked = supp['id'] in today_checks
                    check = Gtk.CheckButton()
                    check.set_active(is_checked)
                    check.connect('toggled', self.on_toggle_supp_check, supp['id'])
                    row.pack_start(check, False, False, 0)

                    name_lbl = Gtk.Label(label=supp['name'])
                    name_lbl.set_halign(Gtk.Align.START)
                    name_lbl.set_hexpand(True)
                    name_lbl.get_style_context().add_class('todo-text')
                    if is_checked:
                        esc = GLib.markup_escape_text(supp['name'])
                        name_lbl.set_markup(f'<s><span foreground="#666">{esc}</span></s>')
                    row.pack_start(name_lbl, True, True, 0)

                    self.supp_check_box.pack_start(row, False, False, 0)

        # 진행률 (항상 전체 기준)
        total = len(all_supplements)
        today_checks = self.get_today_supp_checks()
        checked = sum(1 for s in all_supplements if s['id'] in today_checks)
        self.supp_progress_label.set_text(f'복용: {checked}/{total}')
        self.supp_progress_bar.set_fraction(checked / total if total > 0 else 0)

        self.supp_check_box.show_all()

    def refresh_supp_list(self):
        for child in self.supp_list_box.get_children():
            self.supp_list_box.remove(child)

        supplements = self.data.get('supplements', [])
        if not supplements:
            e = Gtk.Label(label='등록된 영양제가 없습니다.')
            e.get_style_context().add_class('hint-label')
            e.set_margin_top(8)
            e.set_margin_bottom(8)
            self.supp_list_box.pack_start(e, False, False, 0)
        else:
            sorted_supps = sorted(supplements, key=lambda s: SLOT_ORDER.index(s['slot']) if s['slot'] in SLOT_ORDER else 99)
            for supp in sorted_supps:
                row = Gtk.Box(spacing=8)
                row.set_margin_top(2)
                row.set_margin_bottom(2)
                lbl = Gtk.Label(label=supp['name'])
                lbl.set_halign(Gtk.Align.START)
                lbl.set_hexpand(True)
                row.pack_start(lbl, True, True, 0)

                badge = Gtk.Label(label=SLOT_LABELS.get(supp['slot'], supp['slot']))
                badge.get_style_context().add_class('supp-slot-badge')
                row.pack_start(badge, False, False, 0)

                db = Gtk.Button(label='\u2715')
                db.get_style_context().add_class('delete-btn')
                db.set_relief(Gtk.ReliefStyle.NONE)
                db.connect('clicked', self.on_delete_supplement, supp['id'])
                row.pack_start(db, False, False, 0)

                self.supp_list_box.pack_start(row, False, False, 0)
        self.supp_list_box.show_all()

    def on_add_supplement(self, widget):
        name = self.supp_name_entry.get_text().strip()
        if not name:
            return
        slot = self.supp_slot_combo.get_active_id()
        if not slot:
            slot = 'morning-after'
        supp_id = int(datetime.now().timestamp() * 1000)
        self.data['supplements'].append({
            'id': supp_id,
            'name': name,
            'slot': slot,
        })
        save_data(self.data)
        GLib.idle_add(self._clear_entry, self.supp_name_entry)
        self.refresh_supp_checklist()
        self.refresh_supp_list()

    def on_delete_supplement(self, widget, supp_id):
        self.data['supplements'] = [s for s in self.data['supplements'] if s['id'] != supp_id]
        for date_checks in self.data['supplement_checks'].values():
            if supp_id in date_checks:
                date_checks.remove(supp_id)
        save_data(self.data)
        self.refresh_supp_checklist()
        self.refresh_supp_list()

    def on_toggle_supp_check(self, widget, supp_id):
        today = get_today()
        checks = self.data['supplement_checks'].setdefault(today, [])
        if supp_id in checks:
            checks.remove(supp_id)
        else:
            checks.append(supp_id)
        save_data(self.data)
        self.refresh_supp_checklist()

    def refresh_supp_missed(self):
        for child in self.supp_missed_box.get_children():
            self.supp_missed_box.remove(child)

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        supplements = self.data.get('supplements', [])
        yesterday_checks = self.data['supplement_checks'].get(yesterday, [])
        missed = [s for s in supplements if s['id'] not in yesterday_checks]

        if not missed:
            self.supp_missed_card.hide()
            return

        self.supp_missed_card.show()

        title = Gtk.Label(label='어제 안 드신 영양제')
        title.get_style_context().add_class('supp-missed-title')
        title.set_halign(Gtk.Align.START)
        self.supp_missed_box.pack_start(title, False, False, 0)

        names = ', '.join(s['name'] for s in missed[:3])
        if len(missed) > 3:
            names += f' 외 {len(missed) - 3}개'
        msg = Gtk.Label()
        msg.set_markup(f'<span foreground="#e8a838">어제 {GLib.markup_escape_text(names)}을(를) 안 드셨네요.\n꼭 챙겨 드세요!</span>')
        msg.set_halign(Gtk.Align.START)
        msg.set_line_wrap(True)
        msg.set_size_request(340, -1)
        self.supp_missed_box.pack_start(msg, False, False, 4)

        sorted_missed = sorted(missed, key=lambda s: SLOT_ORDER.index(s['slot']) if s['slot'] in SLOT_ORDER else 99)
        for supp in sorted_missed:
            row = Gtk.Box(spacing=8)
            row.set_margin_top(2)
            row.set_margin_bottom(2)
            row.set_margin_start(4)

            lbl = Gtk.Label(label=f'{supp["name"]}')
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)
            lbl.get_style_context().add_class('todo-text')
            row.pack_start(lbl, True, True, 0)

            badge = Gtk.Label(label=SLOT_LABELS.get(supp['slot'], ''))
            badge.get_style_context().add_class('supp-slot-badge')
            row.pack_start(badge, False, False, 0)

            btn = Gtk.Button(label='먹었어요')
            btn.get_style_context().add_class('supp-taken-btn')
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_tooltip_text('어제 실제로 먹었으면 체크')
            btn.connect('clicked', self.on_mark_supp_yesterday, supp['id'])
            row.pack_start(btn, False, False, 0)

            self.supp_missed_box.pack_start(row, False, False, 0)

        self.supp_missed_box.show_all()

    def on_mark_supp_yesterday(self, widget, supp_id):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        checks = self.data['supplement_checks'].setdefault(yesterday, [])
        if supp_id not in checks:
            checks.append(supp_id)
        save_data(self.data)
        self.refresh_supp_missed()

    def on_supp_filter(self, widget, filter_val):
        self.supp_filter = filter_val
        for fval, btn in self.supp_filter_btns.items():
            btn.get_style_context().remove_class('supp-filter-btn-active')
            btn.get_style_context().remove_class('supp-filter-btn')
            if fval == filter_val:
                btn.get_style_context().add_class('supp-filter-btn-active')
            else:
                btn.get_style_context().add_class('supp-filter-btn')
        self.refresh_supp_checklist()

    def on_tray_supp_toggle(self, widget, supp_id):
        today = get_today()
        checks = self.data['supplement_checks'].setdefault(today, [])
        if supp_id in checks:
            checks.remove(supp_id)
        else:
            checks.append(supp_id)
        save_data(self.data)
        self.update_indicator_label()
        self.build_tray_menu()
        if self.window and self.window.get_visible() and self.supp_visible:
            self.refresh_supp_checklist()

    # --- 이벤트 핸들러 ---

    def _clear_entry(self, entry):
        entry.reset_im_context()
        entry.set_text('')
        return False

    def on_entry_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_space or event.keyval == Gdk.KEY_period:
            widget.reset_im_context()
        return False

    def on_edit_todo(self, widget, idx):
        todos = self.get_current_todos()
        if not (0 <= idx < len(todos)):
            return
        dlg = Gtk.Dialog(title='할일 수정', transient_for=self.window, modal=True)
        dlg.set_default_size(300, -1)
        box = dlg.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(16)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        entry = Gtk.Entry()
        entry.set_text(todos[idx]['text'])
        entry.connect('activate', lambda w: dlg.response(Gtk.ResponseType.OK))
        entry.connect('key-press-event', self.on_entry_key_press)
        box.pack_start(entry, False, False, 0)
        bb = Gtk.Box(spacing=8)
        bb.set_halign(Gtk.Align.END)
        cb = Gtk.Button(label='취소')
        cb.connect('clicked', lambda w: dlg.response(Gtk.ResponseType.CANCEL))
        bb.pack_start(cb, False, False, 0)
        ob = Gtk.Button(label='저장')
        ob.connect('clicked', lambda w: dlg.response(Gtk.ResponseType.OK))
        bb.pack_start(ob, False, False, 0)
        box.pack_start(bb, False, False, 0)
        dlg.show_all()
        if dlg.run() == Gtk.ResponseType.OK:
            new = entry.get_text().strip()
            if new:
                todos[idx]['text'] = new
                save_data(self.data)
                self.refresh_todo_list()
                self.update_indicator_label()
                self.build_tray_menu()
                if self.cal_visible:
                    self.build_calendar_grid()
        dlg.destroy()

    def on_add_todo(self, widget):
        text = self.input_entry.get_text().strip()
        if not text:
            return
        todos = self.data['todos_by_date'].setdefault(self.selected_date, [])
        todos.append({'text': text, 'completed': False, 'daily': False})
        save_data(self.data)
        GLib.idle_add(self._clear_entry, self.input_entry)
        self.refresh_todo_list()
        self.update_indicator_label()
        self.build_tray_menu()
        if self.cal_visible:
            self.build_calendar_grid()

    def on_toggle_todo(self, widget, idx):
        todos = self.get_current_todos()
        if 0 <= idx < len(todos):
            todos[idx]['completed'] = widget.get_active()
            save_data(self.data)
            self.refresh_todo_list()
            self.update_indicator_label()
            self.build_tray_menu()
            if self.cal_visible:
                self.build_calendar_grid()

    def on_delete_todo(self, widget, idx):
        todos = self.get_current_todos()
        if 0 <= idx < len(todos):
            del todos[idx]
            save_data(self.data)
            self.refresh_todo_list()
            self.update_indicator_label()
            self.build_tray_menu()
            if self.cal_visible:
                self.build_calendar_grid()

    def on_add_daily(self, widget):
        text = self.daily_entry.get_text().strip()
        if not text:
            return
        self.data['daily_tasks'].append({'text': text})
        today = get_today()
        today_todos = self.data['todos_by_date'].get(today, [])
        today_todos.append({'text': text, 'completed': False, 'daily': True})
        self.data['todos_by_date'][today] = today_todos
        save_data(self.data)
        GLib.idle_add(self._clear_entry, self.daily_entry)
        self.refresh_daily_list()
        self.refresh_todo_list()
        self.update_indicator_label()
        self.build_tray_menu()

    def on_delete_daily(self, widget, idx):
        if 0 <= idx < len(self.data['daily_tasks']):
            del self.data['daily_tasks'][idx]
            save_data(self.data)
            self.refresh_daily_list()

    def on_open_window(self, widget=None):
        if not self.check_password():
            return
        self.refresh_todo_list()
        self.refresh_daily_list()
        self.refresh_overdue_list()
        self.refresh_supp_checklist()
        self.refresh_supp_list()
        self.refresh_supp_missed()
        if self.cal_visible:
            self.build_calendar_grid()
        self.window.show_all()
        if not self.cal_visible:
            self.cal_panel.hide()
        if not self.supp_visible:
            self.supp_container.hide()
        else:
            self.todo_container.hide()
        self.window.present()

    def on_window_close(self, widget, event):
        self.window.hide()
        return True

    def on_quit(self, widget):
        Gtk.main_quit()

    def periodic_check(self):
        today = get_today()
        if today not in self.data.get('initialized_dates', []):
            get_todos_for_date(self.data, today)
            self.update_indicator_label()
            self.build_tray_menu()
        return True


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = TodoTrayApp()
    if not app.check_password():
        return
    app.window.show_all()
    if not app.cal_visible:
        app.cal_panel.hide()
    if not app.supp_visible:
        app.supp_container.hide()
    else:
        app.todo_container.hide()
    app.window.present()
    Gtk.main()


if __name__ == '__main__':
    main()
