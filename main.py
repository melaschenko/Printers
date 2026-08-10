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
        self.history_nozzle = [nozzle_temp + (random.random() - 0.5) * 3 for _ in range(90)]
        self.history_bed = [bed_temp + (random.random() - 0.5) * 1.5 for _ in range(90)]

    def update_simulation(self) -> None:
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
            self.nozzle_temp = self.target_nozzle + (random.random() - 0.5) * 1.5
            self.bed_temp = self.target_bed + (random.random() - 0.5) * 0.6
        elif self.status == 'idle' and self.target_nozzle == 0:
            self.nozzle_temp += (24 - self.nozzle_temp) * 0.03
            self.bed_temp += (22 - self.bed_temp) * 0.03

        self.history_nozzle.append(self.nozzle_temp)
        self.history_bed.append(self.bed_temp)
        if len(self.history_nozzle) > 90:
            self.history_nozzle.pop(0)
        if len(self.history_bed) > 90:
            self.history_bed.pop(0)


class PrinterFarm:
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


# ================================================================
#  UI-КОМПОНЕНТЫ (без Canvas, без GridView, без сложных стилей)
# ================================================================
class PrinterListPanel:
    def __init__(self, farm: PrinterFarm, on_select: Callable[[int], None]):
        self.farm = farm
        self.on_select = on_select
        self.printer_column = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)
        self.container = ft.Container(
            content=ft.Column([
                ft.Text('Принтеры (10)', size=11, weight=ft.FontWeight.W_600, color='#6b7280'),
                self.printer_column,
            ], spacing=8),
            width=260, padding=8, bgcolor='#131720',
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
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=indicator),
                    ft.Text(p.name, weight=ft.FontWeight.W_600, size=13, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(status_txt, size=10, color='#9ca3af'),
                ], spacing=8, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(p.material, size=10, color='#6b7280'),
                    ft.Text(f"{p.progress}%", size=10, color='#6b7280') if p.status == 'printing' else ft.Text(''),
                ], spacing=5),
                ft.ProgressBar(
                    value=p.progress / 100 if p.status == 'printing' else 0,
                    color='#4ec9b0', bgcolor='#252b36', height=3, border_radius=2,
                ) if p.status == 'printing' else ft.Container(height=3),
            ], spacing=2),
            padding=10, border_radius=8,
            bgcolor='#7c6ff720' if active else '#1a1f2b',
            on_click=lambda e, pid=p.id: self.on_select(pid),
        )


class StatusCard:
    def __init__(self, farm: PrinterFarm):
        self.farm = farm
        self.status_dot = ft.Container(width=10, height=10, border_radius=5, bgcolor='#4ec9b0')
        self.badge_text = ft.Text('Печать', size=11, weight=ft.FontWeight.W_600)
        self.status_badge = ft.Container(
            content=self.badge_text,
            padding=5,
            border_radius=12,
            bgcolor='#4ec9b020',
        )
        self.name_display = ft.Text(size=14, weight=ft.FontWeight.W_600)
        self.progress_val = ft.Text(size=18, weight=ft.FontWeight.W_700, font_family='monospace', color='#4ec9b0')
        self.remaining_val = ft.Text(size=16, weight=ft.FontWeight.W_700, font_family='monospace')
        self.nozzle_val = ft.Text(size=16, weight=ft.FontWeight.W_700, color='#f97316', font_family='monospace')
        self.bed_val = ft.Text(size=16, weight=ft.FontWeight.W_700, color='#f97316', font_family='monospace')
        self.file_val = ft.Text(size=11, color='#6b7280')
        self.layer_val = ft.Text(size=11, color='#6b7280')

        self.container = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Row([self.status_dot, self.name_display], spacing=8),
                    self.status_badge,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    self._tile('ПРОГРЕСС', self.progress_val),
                    self._tile('ОСТАЛОСЬ', self.remaining_val),
                ], spacing=8),
                ft.Row([
                    self._tile('СОПЛО', self.nozzle_val),
                    self._tile('СТОЛ', self.bed_val),
                ], spacing=8),
                ft.Row([ft.Text('Файл: ', size=11, color='#6b7280'), self.file_val,
                        ft.Text(' | Слой: ', size=11, color='#6b7280'), self.layer_val], spacing=4),
            ], spacing=10),
            padding=16, border_radius=12, bgcolor='#1a1f2b',
        )

    def _tile(self, label: str, value: ft.Text) -> ft.Container:
        return ft.Container(
            ft.Column([ft.Text(label, size=9, color='#6b7280'), value]),
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
        else:
            self.status_badge.bgcolor = '#636b7820'
            self.badge_text.color = '#9ca3af'

        self.name_display.value = p.name
        self.progress_val.value = f"{p.progress}%" if p.status == 'printing' else '—'
        self.remaining_val.value = format_time(p.remaining) if p.status == 'printing' else '—'
        self.nozzle_val.value = f"{int(p.nozzle_temp)}°C"
        self.bed_val.value = f"{int(p.bed_temp)}°C"
        self.file_val.value = p.file
        self.layer_val.value = f"{p.current_layer} / {p.total_layers}" if p.status == 'printing' else '—'


class SimpleCameraView:
    """Замена камере — просто текстовая информация."""
    def __init__(self):
        self.camera_text = ft.Text('Вид с камеры', size=16, color='#666666')
        self.layer_info = ft.Text('', size=12, color='#9ca3af')
        self.container = ft.Container(
            content=ft.Column([
                self.camera_text,
                self.layer_info,
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            border_radius=8, bgcolor='#000000',
            padding=20, height=180,
        )

    def build(self) -> ft.Container:
        return self.container

    def update(self, printer: PrinterModel) -> None:
        if printer.status == 'printing':
            self.camera_text.value = 'Печать активна'
            self.layer_info.value = f'Слой: {printer.current_layer}/{printer.total_layers}'
        elif printer.status == 'idle':
            self.camera_text.value = 'Принтер готов'
            self.layer_info.value = ''
        else:
            self.camera_text.value = 'Нет данных'
            self.layer_info.value = ''


class SimpleTempChart:
    """Замена графику температур — текстовые индикаторы."""
    def __init__(self):
        self.nozzle_label = ft.Text('Сопло: --°C', size=12, color='#f97316', weight=ft.FontWeight.BOLD)
        self.bed_label = ft.Text('Стол: --°C', size=12, color='#f59e0b', weight=ft.FontWeight.BOLD)
        self.nozzle_progress = ft.ProgressBar(value=0, color='#f97316', bgcolor='#252b36', height=4, border_radius=2)
        self.bed_progress = ft.ProgressBar(value=0, color='#f59e0b', bgcolor='#252b36', height=4, border_radius=2)
        self.container = ft.Container(
            content=ft.Column([
                self.nozzle_label,
                self.nozzle_progress,
                self.bed_label,
                self.bed_progress,
            ], spacing=10),
            border_radius=8, bgcolor='#0a0d12',
            padding=16, height=160,
        )

    def build(self) -> ft.Container:
        return self.container

    def update(self, printer: PrinterModel) -> None:
        self.nozzle_label.value = f"Сопло: {int(printer.nozzle_temp)}°C"
        self.bed_label.value = f"Стол: {int(printer.bed_temp)}°C"
        if printer.target_nozzle > 0:
            self.nozzle_progress.value = min(1.0, printer.nozzle_temp / printer.target_nozzle)
        else:
            self.nozzle_progress.value = 0
        if printer.target_bed > 0:
            self.bed_progress.value = min(1.0, printer.bed_temp / printer.target_bed)
        else:
            self.bed_progress.value = 0


class GCodeTerminal:
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
            bgcolor='#7c6ff7', color='white',
        )
        self.container = ft.Container(
            content=ft.Column([
                ft.Row([ft.Text('💻 G-Code терминал', size=11, color='#9ca3af'),
                        ft.Text('● подключено', size=11, color='#34d399')], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.output,
                ft.Row([self.input, self.send_btn], spacing=0),
            ], spacing=4),
            border_radius=10, bgcolor='#0a0d12',
            padding=0,
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
    def __init__(self, on_pause, on_cancel, on_home, on_cool, on_extrude, on_retract):
        self.btn_pause = ft.ElevatedButton(
            text='⏯️ Пауза', on_click=on_pause,
            bgcolor='#34d39920', color='#34d399',
        )
        self.btn_cancel = ft.ElevatedButton(
            text='⏹️ Отмена', on_click=on_cancel,
            bgcolor='#ef444420', color='#ef4444',
        )
        base_style = {'bgcolor': '#1a1f2b', 'color': 'white'}
        self.btn_home = ft.ElevatedButton(text='🏠 Home', on_click=on_home, **base_style)
        self.btn_cool = ft.ElevatedButton(text='❄️ Охладить', on_click=on_cool, **base_style)
        self.btn_extrude = ft.ElevatedButton(text='⬆️ Экструзия', on_click=on_extrude, **base_style)
        self.btn_retract = ft.ElevatedButton(text='⬇️ Ретракция', on_click=on_retract, **base_style)
        self.row = ft.Row([self.btn_pause, self.btn_cancel, self.btn_home, self.btn_cool, self.btn_extrude, self.btn_retract],
                          spacing=8, wrap=True)

    def update_state(self, is_printing: bool, is_paused: bool) -> None:
        self.btn_pause.disabled = not is_printing
        self.btn_cancel.disabled = not is_printing
        self.btn_pause.text = '▶️ Возобновить' if is_paused else '⏯️ Пауза'

    def build(self) -> ft.Row:
        return self.row


# ================================================================
#  ДАННЫЕ И ГЛАВНОЕ ПРИЛОЖЕНИЕ
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
    page.title = "PrintNexus Pro"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window_width = 1280
    page.window_height = 820
    page.bgcolor = '#0b0e14'

    farm = PrinterFarm(PRINTERS_DATA)
    status_card = StatusCard(farm)
    camera_view = SimpleCameraView()
    temp_chart = SimpleTempChart()

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
        camera_view.update(farm.active_printer)
        temp_chart.update(farm.active_printer)
        controls.update_state(
            is_printing=(farm.active_printer.status == 'printing'),
            is_paused=farm.active_printer.paused
        )
        page.update()

    def simulation_tick():
        farm.update_all_simulations()
        refresh_ui()

    # Исправлено: set_interval → add_interval для старых версий Flet
    page.add_interval(1, simulation_tick)
    refresh_ui()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8550))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port)
