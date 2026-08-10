import flet as ft
import time
import math
import random
from datetime import datetime
from typing import List, Callable
import os

# ================================================================
#  МОДЕЛИ ДАННЫХ
# ================================================================
class PrinterModel:
    """Состояние одного 3D-принтера и симуляция."""
    def __init__(self, pid: int, name: str, status: str, material: str, file: str,
                 progress: float, total_layers: int, current_layer: int,
                 nozzle_temp: float, target_nozzle: float, bed_temp: float,
                 target_bed: float, remaining: int, color: str):
        self.id = pid
        self.name = name
        self.status = status          # 'printing', 'idle', 'offline', 'error'
        self.material = material
        self.file = file
        self.progress = progress
        self.total_layers = total_layers
        self.current_layer = current_layer
        self.nozzle_temp = nozzle_temp
        self.target_nozzle = target_nozzle
        self.bed_temp = bed_temp
        self.target_bed = target_bed
        self.remaining = remaining
        self.paused = False
        self.color = color
        self.layer_progress = progress / 100.0 if total_layers > 0 else 0.0
        # история температур (последние 90 точек)
        self.history_nozzle = [nozzle_temp + (random.random() - 0.5) * 3 for _ in range(90)]
        self.history_bed = [bed_temp + (random.random() - 0.5) * 1.5 for _ in range(90)]

    def update_simulation(self) -> None:
        """Обновление параметров (вызывается раз в секунду)."""
        if self.status == 'printing' and not self.paused:
            self.progress += 0.04
            if self.progress >= 100:
                self.progress = 100
                self.status = 'idle'
                self.file = '—'
                self.remaining = 0
                self.current_layer = self.total_layers
                self.layer_progress = 1.0
                self.target_nozzle = 0
                self.target_bed = 0
            else:
                self.remaining = max(0, self.remaining - 1)
                self.current_layer = int(self.progress / 100 * self.total_layers)
                self.layer_progress = self.progress / 100.0
            # имитация колебаний температуры
            self.nozzle_temp = self.target_nozzle + (random.random() - 0.5) * 1.5
            self.bed_temp = self.target_bed + (random.random() - 0.5) * 0.6
        elif self.status == 'idle' and self.target_nozzle == 0:
            self.nozzle_temp += (24 - self.nozzle_temp) * 0.03
            self.bed_temp += (22 - self.bed_temp) * 0.03

        # сдвиг истории
        self.history_nozzle.append(self.nozzle_temp)
        self.history_bed.append(self.bed_temp)
        if len(self.history_nozzle) > 90:
            self.history_nozzle.pop(0)
        if len(self.history_bed) > 90:
            self.history_bed.pop(0)


class PrinterFarm:
    """Управление списком принтеров и активным."""
    def __init__(self, printers: List[PrinterModel]):
        self.printers = printers
        self.active_id = 0

    @property
    def active_printer(self) -> PrinterModel:
        return self.printers[self.active_id]

    def switch_to(self, pid: int) -> None:
        if 0 <= pid < len(self.printers):
            self.active_id = pid

    def toggle_pause_active(self) -> None:
        p = self.active_printer
        if p.status == 'printing':
            p.paused = not p.paused

    def cancel_print_active(self) -> None:
        p = self.active_printer
        if p.status == 'printing':
            p.status = 'idle'
            p.paused = False
            p.progress = 0
            p.file = '—'
            p.remaining = 0
            p.current_layer = 0
            p.layer_progress = 0
            p.target_nozzle = 0
            p.target_bed = 0

    def update_all_simulations(self) -> None:
        for p in self.printers:
            p.update_simulation()


# ================================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ================================================================
def format_time(seconds: int) -> str:
    if seconds <= 0:
        return '< 1м'
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f'{h}ч {m}м' if h else f'{m}м'


def get_status_indicator_color(status: str, paused: bool = False) -> str:
    if status == 'printing':
        return '#4ec9b0' if not paused else '#f59e0b'
    elif status == 'idle':
        return '#34d399'
    elif status == 'error':
        return '#ef4444'
    return '#636b78'


def get_status_text(status: str, paused: bool = False) -> str:
    if status == 'printing':
        return 'Пауза' if paused else 'Печать'
    elif status == 'idle':
        return 'Готов'
    elif status == 'error':
        return 'Ошибка'
    return 'Офлайн'


def all_border(width: float, color: str) -> ft.border.Border:
    side = ft.border.BorderSide(width, color)
    return ft.border.Border(top=side, left=side, bottom=side, right=side)


# ================================================================
#  UI-КОМПОНЕНТЫ
# ================================================================
class PrinterListPanel:
    """Боковая панель со списком принтеров."""
    def __init__(self, farm: PrinterFarm, on_select: Callable[[int], None]):
        self.farm = farm
        self.on_select = on_select
        self.printer_column = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)
        self.container = ft.Container(
            content=ft.Column([
                ft.Text('Принтеры (10)', size=11, weight=ft.FontWeight.W_600, color=ft.colors.GREY_500),
                self.printer_column,
            ], spacing=8),
            width=260, padding=8, bgcolor='#131720',
            border=ft.border.only(right=ft.border.BorderSide(1, '#252b36')),
        )

    def build(self) -> ft.Container:
        self.refresh()
        return self.container

    def refresh(self) -> None:
        self.printer_column.controls.clear()
        for p in self.farm.printers:
            self.printer_column.controls.append(self._card(p))

    def _card(self, p: PrinterModel) -> ft.Container:
        active = p.id == self.farm.active_id
        indicator = get_status_indicator_color(p.status, p.paused)
        status_txt = get_status_text(p.status, p.paused)
        if active:
            border = all_border(2, '#7c6ff7')
        else:
            border = all_border(2, '#252b36')
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=indicator),
                    ft.Text(p.name, weight=ft.FontWeight.W_600, size=13, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(status_txt, size=10, color=ft.colors.GREY_400),
                ], spacing=8, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(p.material, size=10, color=ft.colors.GREY_500),
                    ft.Text(f"{p.progress}%", size=10, color=ft.colors.GREY_500) if p.status == 'printing' else ft.Text(''),
                ], spacing=5),
                ft.ProgressBar(
                    value=p.progress / 100 if p.status == 'printing' else 0,
                    color='#4ec9b0', bgcolor='#252b36', height=3, border_radius=2,
                ) if p.status == 'printing' else ft.Container(height=3),
            ], spacing=2),
            padding=10, border_radius=8,
            bgcolor='#1a1f2b' if not active else '#7c6ff720',
            border=border,
            on_click=lambda e, pid=p.id: self.on_select(pid),
            animate=ft.Animation(200, curve='ease'),
        )


class StatusCard:
    """Карточка с информацией о выбранном принтере."""
    def __init__(self, farm: PrinterFarm):
        self.farm = farm
        self.status_dot = ft.Container(width=10, height=10, border_radius=5, bgcolor='#4ec9b0')
        # Бейдж теперь — контейнер с текстом внутри
        self.badge_text = ft.Text('Печать', size=11, weight=ft.FontWeight.W_600)
        self.status_badge = ft.Container(
            content=self.badge_text,
            padding=ft.padding.only(left=8, top=3, right=8, bottom=3),
            border_radius=12,
            bgcolor='#4ec9b020',
            border=all_border(1, '#4ec9b040'),
        )
        self.name_display = ft.Text(size=14, weight=ft.FontWeight.W_600)
        self.progress_val = ft.Text(size=18, weight=ft.FontWeight.W_700, font_family='monospace', color='#4ec9b0')
        self.remaining_val = ft.Text(size=16, weight=ft.FontWeight.W_700, font_family='monospace')
        self.nozzle_val = ft.Text(size=16, weight=ft.FontWeight.W_700, color='#f97316', font_family='monospace')
        self.bed_val = ft.Text(size=16, weight=ft.FontWeight.W_700, color='#f97316', font_family='monospace')
        self.file_val = ft.Text(size=11, color=ft.colors.GREY_500)
        self.layer_val = ft.Text(size=11, color=ft.colors.GREY_500)

        self.container = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Row([self.status_dot, self.name_display], spacing=8),
                    self.status_badge,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.GridView([
                    self._tile('ПРОГРЕСС', self.progress_val),
                    self._tile('ОСТАЛОСЬ', self.remaining_val),
                    self._tile('СОПЛО', self.nozzle_val),
                    self._tile('СТОЛ', self.bed_val),
                ], runs_count=2, max_extent=100, spacing=8, run_spacing=8),
                ft.Row([ft.Text('Файл: ', size=11, color=ft.colors.GREY_500), self.file_val,
                        ft.Text(' | Слой: ', size=11, color=ft.colors.GREY_500), self.layer_val], spacing=4),
            ], spacing=10),
            padding=16, border_radius=12, bgcolor='#1a1f2b',
            border=all_border(1, '#252b36'),
        )

    def _tile(self, label: str, value: ft.Text) -> ft.Container:
        return ft.Container(
            ft.Column([ft.Text(label, size=9, color=ft.colors.GREY_500), value]),
            padding=8, bgcolor='#0f131c', border_radius=6,
        )

    def build(self) -> ft.Container:
        self.update()
        return self.container

    def update(self) -> None:
        p = self.farm.active_printer
        self.status_dot.bgcolor = get_status_indicator_color(p.status, p.paused)
        badge_text = get_status_text(p.status, p.paused)
        self.badge_text.value = badge_text
        if p.status == 'printing':
            self.status_badge.bgcolor = '#4ec9b020' if not p.paused else '#f59e0b20'
            self.badge_text.color = '#4ec9b0' if not p.paused else '#f59e0b'
            self.status_badge.border = all_border(1, '#4ec9b040' if not p.paused else '#f59e0b40')
        else:
            self.status_badge.bgcolor = '#636b7820'
            self.badge_text.color = ft.colors.GREY_400
            self.status_badge.border = all_border(1, '#636b7840')

        self.name_display.value = p.name
        self.progress_val.value = f"{p.progress}%" if p.status == 'printing' else '—'
        self.remaining_val.value = format_time(p.remaining) if p.status == 'printing' else '—'
        self.nozzle_val.value = f"{int(p.nozzle_temp)}°C"
        self.bed_val.value = f"{int(p.bed_temp)}°C"
        self.file_val.value = p.file
        self.layer_val.value = f"{p.current_layer} / {p.total_layers}" if p.status == 'printing' else '—'


class CameraView:
    """Симуляция вида с камеры."""
    def __init__(self):
        self.canvas = ft.Canvas(width=400, height=180)
        self.container = ft.Container(
            content=self.canvas,
            border_radius=8, bgcolor='#000000',
            border=all_border(1, '#252b36'),
            padding=0, clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

    def build(self) -> ft.Container:
        return self.container

    def draw(self, printer: PrinterModel) -> None:
        self.canvas.shapes.clear()
        w = self.container.width or 400
        h = self.container.height or 180
        if w <= 0 or h <= 0:
            return
        bed_w, bed_h = w * 0.7, h * 0.45
        bed_x, bed_y = (w - bed_w) / 2, h * 0.4
        self.canvas.shapes.append(ft.Rect(bed_x, bed_y, bed_w, bed_h, paint=ft.Paint(color='#1a1a1a')))
        self.canvas.shapes.append(ft.Rect(bed_x, bed_y, bed_w, bed_h, paint=ft.Paint(color='#333333', style=ft.PaintingStyle.STROKE, stroke_width=1)))

        if printer.status == 'printing' and not printer.paused:
            obj_w, obj_h = bed_w * 0.35, bed_h * 0.6
            obj_x = bed_x + bed_w/2 - obj_w/2
            obj_bottom = bed_y + bed_h - 4
            obj_top = obj_bottom - obj_h * printer.layer_progress
            self.canvas.shapes.append(ft.Rect(obj_x, max(obj_top, bed_y), obj_w, min(obj_bottom - obj_top, obj_h),
                                              paint=ft.Paint(color='#e8d5b7')))
            nozzle_x = obj_x + obj_w/2 + math.sin(time.time() * 2 + printer.id) * obj_w * 0.3
            nozzle_y = obj_top - 8
            self.canvas.shapes.append(ft.Circle(nozzle_x, nozzle_y, 5, paint=ft.Paint(color='#ff4444')))
        elif printer.status == 'idle':
            self.canvas.shapes.append(ft.Text(w/2, h/2, 'Принтер готов', style=ft.TextStyle(color='#666666', size=12)))
        self.canvas.shapes.append(ft.Rect(4, 4, w-8, h-8, paint=ft.Paint(color='#ffffff20', style=ft.PaintingStyle.STROKE, stroke_width=1)))


class TemperatureChart:
    """График температур сопла и стола."""
    def __init__(self):
        self.canvas = ft.Canvas(width=400, height=160)
        self.container = ft.Container(
            content=self.canvas,
            border_radius=8, bgcolor='#0a0d12',
            border=all_border(1, '#1a1f2b'),
            padding=0,
        )

    def build(self) -> ft.Container:
        return self.container

    def draw(self, printer: PrinterModel) -> None:
        self.canvas.shapes.clear()
        w = self.container.width or 400
        h = self.container.height or 160
        if w <= 0 or h <= 0:
            return
        m = {'top': 8, 'right': 20, 'bottom': 16, 'left': 34}
        pw, ph = w - m['left'] - m['right'], h - m['top'] - m['bottom']
        if pw <= 0 or ph <= 0:
            return
        self.canvas.shapes.append(ft.Rect(0, 0, w, h, paint=ft.Paint(color='#0a0d12')))

        all_temps = printer.history_nozzle + printer.history_bed + [printer.target_nozzle, printer.target_bed]
        min_t = max(0, min(all_temps) - 5)
        max_t = max(all_temps) + 10
        if max_t - min_t < 30:
            min_t = int(min_t // 5) * 5
            max_t = min_t + 40

        def tx(i): return m['left'] + (i / 89) * pw
        def ty(val): return m['top'] + ph - ((val - min_t) / (max_t - min_t)) * ph

        for i in range(5):
            y = m['top'] + (ph / 4) * i
            self.canvas.shapes.append(ft.Line(m['left'], y, w - m['right'], y, paint=ft.Paint(color='#1a1f2b', stroke_width=0.5)))
        if printer.target_nozzle > 0:
            yt = ty(printer.target_nozzle)
            self.canvas.shapes.append(ft.Line(m['left'], yt, w - m['right'], yt, paint=ft.Paint(color='#4ec9b060', stroke_width=1, stroke_dash_pattern=[5, 3])))

        bed_pts = [ft.Offset(tx(i), ty(v)) for i, v in enumerate(printer.history_bed)]
        for i in range(1, len(bed_pts)):
            self.canvas.shapes.append(ft.Line(bed_pts[i-1].x, bed_pts[i-1].y, bed_pts[i].x, bed_pts[i].y,
                                              paint=ft.Paint(color='#f59e0b', stroke_width=2)))
        nozzle_pts = [ft.Offset(tx(i), ty(v)) for i, v in enumerate(printer.history_nozzle)]
        for i in range(1, len(nozzle_pts)):
            self.canvas.shapes.append(ft.Line(nozzle_pts[i-1].x, nozzle_pts[i-1].y, nozzle_pts[i].x, nozzle_pts[i].y,
                                              paint=ft.Paint(color='#f97316', stroke_width=2.5, stroke_cap=ft.StrokeCap.ROUND)))
        self.canvas.shapes.append(ft.Text(m['left']+4, m['top']+2, f"Сопло: {int(printer.history_nozzle[-1])}°C",
                                          style=ft.TextStyle(color='#f97316', size=9, weight=ft.FontWeight.BOLD)))
        self.canvas.shapes.append(ft.Text(m['left']+4, m['top']+14, f"Стол: {int(printer.history_bed[-1])}°C",
                                          style=ft.TextStyle(color='#f59e0b', size=9, weight=ft.FontWeight.BOLD)))


class GCodeTerminal:
    """Терминал отправки G-кода."""
    def __init__(self, on_send: Callable[[str], None]):
        self.on_send = on_send
        self.output = ft.TextField(
            read_only=True, multiline=True, min_lines=8, max_lines=12,
            text_style=ft.TextStyle(font_family='monospace', size=11, color='#b0b8c4'),
            bgcolor='#0a0d12', border_radius=8, border_color='#252b36', content_padding=10,
            value="",
        )
        self.input = ft.TextField(
            hint_text='Введите G-code...',
            text_style=ft.TextStyle(font_family='monospace', size=11),
            bgcolor='#0f131c', border_radius=0, border_color='#252b36',
            on_submit=lambda e: self._send(),
        )
        self.send_btn = ft.ElevatedButton(
            'Отправить', on_click=lambda e: self._send(),
            style=ft.ButtonStyle(bgcolor='#7c6ff7', color='white', shape=ft.RoundedRectangleBorder(radius=0)),
        )
        self.container = ft.Container(
            content=ft.Column([
                ft.Row([ft.Text('💻 G-Code терминал', size=11, color=ft.colors.GREY_400),
                        ft.Text('● подключено', size=11, color='#34d399')], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.output,
                ft.Row([self.input, self.send_btn], spacing=0),
            ], spacing=4),
            border_radius=10, bgcolor='#0a0d12',
            border=all_border(1, '#252b36'),
            padding=0, clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

    def _send(self) -> None:
        cmd = self.input.value.strip()
        if cmd:
            self.on_send(cmd)
            self.input.value = ""
        self.input.update()

    def add_line(self, text: str, color: str = 'info') -> None:
        now = datetime.now().strftime('%H:%M:%S')
        prefix = {'cmd': '>', 'ok': '✓', 'warn': '⚠', 'info': 'i'}.get(color, '')
        line = f"[{now}] {prefix} {text}\n"
        self.output.value += line
        lines = self.output.value.split('\n')
        if len(lines) > 50:
            self.output.value = '\n'.join(lines[-50:])

    def build(self) -> ft.Container:
        return self.container


class ControlButtons:
    """Панель кнопок управления."""
    def __init__(self, on_pause, on_cancel, on_home, on_cool, on_extrude, on_retract):
        self.btn_pause = ft.ElevatedButton(
            text='⏯️ Пауза', on_click=on_pause,
            style=ft.ButtonStyle(bgcolor='#34d39920', color='#34d399', shape=ft.RoundedRectangleBorder(radius=8)),
        )
        self.btn_cancel = ft.ElevatedButton(
            text='⏹️ Отмена', on_click=on_cancel,
            style=ft.ButtonStyle(bgcolor='#ef444420', color='#ef4444', shape=ft.RoundedRectangleBorder(radius=8)),
        )
        base_style = ft.ButtonStyle(bgcolor='#1a1f2b', color=ft.colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8))
        self.btn_home = ft.ElevatedButton(text='🏠 Home', on_click=on_home, style=base_style)
        self.btn_cool = ft.ElevatedButton(text='❄️ Охладить', on_click=on_cool, style=base_style)
        self.btn_extrude = ft.ElevatedButton(text='⬆️ Экструзия', on_click=on_extrude, style=base_style)
        self.btn_retract = ft.ElevatedButton(text='⬇️ Ретракция', on_click=on_retract, style=base_style)
        self.row = ft.Row([self.btn_pause, self.btn_cancel, self.btn_home, self.btn_cool, self.btn_extrude, self.btn_retract],
                          spacing=8, wrap=True)

    def update_state(self, is_printing: bool, is_paused: bool) -> None:
        self.btn_pause.disabled = not is_printing
        self.btn_cancel.disabled = not is_printing
        self.btn_pause.text = '▶️ Возобновить' if is_paused else '⏯️ Пауза'

    def build(self) -> ft.Row:
        return self.row


# ================================================================
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ================================================================
PRINTERS_DATA = [
    PrinterModel(0, 'Prusa XL', 'printing', 'PLA', 'gearbox.gcode', 67, 280, 187, 215, 215, 60, 60, 4980, '#7c6ff7'),
    PrinterModel(1, 'Ender 3 V2', 'idle', 'PETG', '—', 0, 0, 0, 24, 0, 22, 0, 0, '#4ec9b0'),
    PrinterModel(2, 'Voron 2.4', 'printing', 'ABS', 'bracket.gcode', 34, 520, 177, 250, 250, 100, 100, 11220, '#f59e0b'),
    PrinterModel(3, 'Bambu X1C', 'printing', 'PLA-CF', 'drone_arm.gcode', 82, 410, 336, 220, 220, 55, 55, 1240, '#a78bfa'),
    PrinterModel(4, 'Anycubic Vyper', 'idle', 'TPU', '—', 0, 0, 0, 23, 0, 21, 0, 0, '#34d399'),
    PrinterModel(5, 'FLSun V400', 'printing', 'ASA', 'fan_duct.gcode', 45, 300, 135, 255, 255, 105, 105, 6800, '#f97316'),
    PrinterModel(6, 'RatRig V-Minion', 'idle', 'PLA', '—', 0, 0, 0, 22, 0, 20, 0, 0, '#eab308'),
    PrinterModel(7, 'Creality K1', 'printing', 'PETG', 'mount.gcode', 91, 180, 164, 240, 240, 80, 80, 520, '#3b82f6'),
    PrinterModel(8, 'Prusa Mini', 'error', 'PLA', 'clamp.gcode', 12, 220, 26, 0, 210, 24, 60, 0, '#ef4444'),
    PrinterModel(9, 'Voron 0.2', 'offline', 'ABS', '—', 0, 0, 0, 0, 0, 0, 0, 0, '#6b7280'),
]


def main(page: ft.Page):
    page.title = "PrintNexus Pro — Управление 3D-принтерами"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window_width = 1280
    page.window_height = 820
    page.bgcolor = '#0b0e14'

    farm = PrinterFarm(PRINTERS_DATA)
    status_card = StatusCard(farm)
    camera_view = CameraView()
    temp_chart = TemperatureChart()

    def handle_gcode(cmd: str):
        terminal.add_line(f"> {cmd}", 'cmd')
        terminal.add_line("OK", 'ok')

    terminal = GCodeTerminal(on_send=handle_gcode)

    def on_pause(e):
        farm.toggle_pause_active()
        terminal.add_line("Пауза/возобновление", 'warn')
        refresh_ui()

    def on_cancel(e):
        dlg = ft.AlertDialog(
            title=ft.Text("Отменить печать?"),
            content=ft.Text("Прогресс будет потерян."),
            actions=[
                ft.TextButton("Закрыть", on_click=lambda e: close_dlg(dlg)),
                ft.TextButton("Да, отменить", on_click=lambda e: execute_cancel(dlg)),
            ],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def execute_cancel(dlg):
        dlg.open = False
        page.update()
        farm.cancel_print_active()
        terminal.add_line("Печать отменена", 'warn')
        refresh_ui()

    def close_dlg(dlg):
        dlg.open = False
        page.update()

    def on_home(e):
        terminal.add_line("> G28", 'cmd')
        terminal.add_line("OK", 'ok')
    def on_cool(e):
        terminal.add_line("> M104 S0 / M140 S0", 'cmd')
        terminal.add_line("OK", 'ok')
    def on_extrude(e):
        terminal.add_line("> G1 E30 F300", 'cmd')
        terminal.add_line("OK", 'ok')
    def on_retract(e):
        terminal.add_line("> G1 E-30 F300", 'cmd')
        terminal.add_line("OK", 'ok')

    controls = ControlButtons(on_pause, on_cancel, on_home, on_cool, on_extrude, on_retract)

    def on_printer_select(pid: int):
        farm.switch_to(pid)
        terminal.add_line(f"Выбран принтер: {farm.active_printer.name}")
        refresh_ui()

    printer_list = PrinterListPanel(farm, on_printer_select)

    left_panel = printer_list.build()
    right_panel = ft.Column([
        ft.Row([status_card.build(), camera_view.build()], spacing=10),
        controls.build(),
        ft.Row([terminal.build(), temp_chart.build()], spacing=10, expand=True),
    ], spacing=10, expand=True)

    page.add(ft.Row([left_panel, right_panel], expand=True))

    def refresh_ui():
        printer_list.refresh()
        status_card.update()
        camera_view.draw(farm.active_printer)
        temp_chart.draw(farm.active_printer)
        controls.update_state(
            is_printing=(farm.active_printer.status == 'printing'),
            is_paused=farm.active_printer.paused
        )
        page.update()

    def simulation_tick():
        farm.update_all_simulations()
        refresh_ui()

    page.set_interval(1, simulation_tick)
    refresh_ui()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8550))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port)
