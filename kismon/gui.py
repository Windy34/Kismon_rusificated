#!/usr/bin/env python3
"""
Copyright (c) 2010, Patrick Salecker
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice,
      this list of conditions and the following disclaimer in
      the documentation and/or other materials provided with the distribution.
    * Neither the name of the author nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""

from kismon.windows import *
from kismon.widgets import *
import kismon.utils as utils

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib


class MainWindow(TemplateWindow):
    def __init__(self, config, client_start, client_stop, map, networks, sources, tracks, client_threads, logger):
        TemplateWindow.__init__(self)
        self.config = config
        self.config_window = None
        self.progress_bar_win = None
        self.client_start = client_start
        self.client_stop = client_stop
        self.networks = networks
        self.map = map
        self.tracks = tracks
        self.logger = logger

        if map is not None:
            self.locate_marker = map.locate_marker
        else:
            self.locate_marker = None

        self.export_networks = {}
        self.networks.notify_add_list["export"] = self.export_add_network
        self.networks.notify_remove_list["export"] = self.export_remove_network

        self.network_list = NetworkList(self.networks, self.locate_marker, self.on_signal_graph, config=config)

        self.gtkwin.set_title("Монитор беспроводных устройств")
        self.gtkwin.connect("window-state-event", self.on_window_state)
        self.gtkwin.connect('configure-event', self.on_configure_event)

        self.gtkwin.set_default_size(self.config["window"]["width"],
                                     self.config["window"]["height"])

        if self.config["window"]["maximized"] is True:
            self.gtkwin.maximize()

        self.network_filter = {}
        self.signal_graphs = {}
        self.sources = sources
        self.client_threads = client_threads

        vbox = Gtk.VBox()
        self.gtkwin.add(vbox)
        vbox.pack_start(self.init_menu(), False, False, 0)

        vpaned_main = Gtk.VPaned()
        vpaned_main.set_position(400)
        vbox.add(vpaned_main)
        hbox = Gtk.HBox()
        vpaned_main.add1(hbox)
        hbox.pack_start(self.network_list.widget, expand=True, fill=True, padding=0)

        self.notebook = Gtk.Notebook()
        vpaned_main.add2(self.notebook)

        self.server_notebook = Gtk.Notebook()
        frame = Gtk.Frame()
        frame.set_label("Servers")
        frame.add(self.server_notebook)
        hbox.pack_end(frame, expand=False, fill=False, padding=2)

        image = Gtk.Image.new_from_icon_name('list-add', Gtk.IconSize.MENU)
        button = Gtk.Button()
        button.props.focus_on_click = False
        button.add(image)
        button.show_all()
        button.set_tooltip_text('Добавить сервер')
        button.connect("clicked", self.on_add_server_clicked)
        self.server_notebook.set_action_widget(button, Gtk.PackType.END)

        self.server_tabs = {}
        for server_id in self.client_threads:
            self.add_server_tab(server_id)

        self.log_list = LogList(self.config["window"])
        self.notebook.append_page(self.log_list.widget)
        self.notebook.set_tab_label_text(self.log_list.widget, "Log")

        self.filter_tab = FilterTab(config=self.config,
                                    networks=self.networks,
                                    networks_queue_progress=self.networks_queue_progress)
        self.notebook.append_page(self.filter_tab.widget)
        self.notebook.set_tab_label_text(self.filter_tab.widget, "Фильтр")

        self.statusbar = Gtk.Statusbar()
        self.statusbar_context = self.statusbar.get_context_id("Запуск...")
        vbox.pack_end(self.statusbar, expand=False, fill=False, padding=0)

        self.gtkwin.show_all()
        self.apply_config()

    def apply_config(self):
        if self.map is None:
            return
        if self.config["window"]["map_position"] == "widget":
            self.on_map_widget(override=True)
        elif self.config["window"]["map_position"] == "window":
            self.on_map_window(override=True)
        else:
            self.on_map_hide(None)

    def on_destroy(self, widget):
        self.logger.debug("Окно закрыто")
        self.gtkwin = None
        Gtk.main_quit()

    def init_menu(self):
        menubar = Gtk.MenuBar()

        file_menu = Gtk.Menu()
        file_menuitem = Gtk.MenuItem.new_with_label("Файл")
        file_menuitem.set_submenu(file_menu)

        file_import = Gtk.MenuItem.new_with_mnemonic('_Открыть')
        file_import.set_label("Импорт Сетей")
        file_import.connect("activate", self.on_file_import)
        file_menu.append(file_import)

        export_menu = Gtk.Menu()
        export_menuitem = Gtk.MenuItem.new_with_mnemonic('Сохранить _Как')
        export_menuitem.set_label("Экспорт Сетей")
        export_menuitem.set_submenu(export_menu)
        file_menu.append(export_menuitem)

        for export_format, extension in (("Kismon", "json"), ("Kismet netxml", "netxml"),
                                         ("Google Earth KMZ", "kmz"), ("MapPoint csv", "csv")):

            menu = Gtk.Menu()
            menuitem = Gtk.MenuItem.new_with_mnemonic('Сохранить _Как')
            menuitem.set_label(export_format)
            menuitem.set_submenu(menu)
            export_menu.append(menuitem)

            for amount in ("Все", "Отфильтровано"):
                item = Gtk.MenuItem.new_with_label(amount)
                item.connect("activate", self.on_file_export, export_format.lower(), extension, amount)
                menu.append(item)

        sep = Gtk.SeparatorMenuItem()
        file_menu.append(sep)

        config_menuitem = Gtk.MenuItem.new_with_mnemonic('_Настройки')
        config_menuitem.connect("activate", self.on_config_window)
        file_menu.append(config_menuitem)

        sep = Gtk.SeparatorMenuItem()
        file_menu.append(sep)

        exit_menuitem = Gtk.MenuItem.new_with_mnemonic('_Выйти')
        exit_menuitem.connect("activate", self.on_destroy)
        file_menu.append(exit_menuitem)

        menubar.append(file_menuitem)

        help_menu = Gtk.Menu()
        help_menuitem = Gtk.MenuItem.new_with_label("Помощь")
        help_menuitem.set_submenu(help_menu)
        menubar.append(help_menuitem)

        #about = Gtk.MenuItem.new_with_mnemonic('_Справка')
        #about.connect("activate", self.on_about_dialog)
        #help_menu.append(about)

        return menubar

    def on_network_filter_regexpr(self, widget, key):
        dialog = Gtk.Dialog("%s (regular expression)" % key.upper())
        dialog.set_transient_for(self.gtkwin)
        entry = Gtk.Entry()
        entry.set_width_chars(100)
        entry.set_text(self.config["filter_regexpr"][key])
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label("Регулярное выражение:", True, True, 0), False, 5, 5)
        hbox.pack_end(entry, True, True, 0)
        dialog.vbox.pack_end(hbox, True, True, 0)
        dialog.add_button("Принять", 1)
        dialog.show_all()
        dialog.run()
        regexpr = entry.get_text()
        dialog.destroy()
        self.config["filter_regexpr"][key] = regexpr
        self.networks.apply_filters()
        self.networks_queue_progress()

    def networks_queue_progress(self):
        if self.progress_bar_win is not None:
            return

        self.progress_bar_max = float(len(self.networks.notify_add_queue))
        if self.networks.queue_task:
            self.progress_bar = Gtk.ProgressBar()
            self.progress_bar.set_text("0.0%%, %s сетей осталось" % len(self.networks.notify_add_queue))
            self.progress_bar.set_show_text(True)
            self.progress_bar.set_fraction(0)

            self.progress_bar_win = Gtk.Window()
            self.progress_bar_win.set_title("Добавление сетей")
            self.progress_bar_win.set_position(Gtk.WindowPosition.CENTER)
            self.progress_bar_win.set_default_size(300, 30)
            self.progress_bar_win.set_modal(True)
            self.progress_bar_win.set_transient_for(self.gtkwin)
            self.progress_bar_win.add(self.progress_bar)
            self.progress_bar_win.show_all()

            def on_delete_event(widget, event):
                return True

            self.progress_bar_win.connect("delete-event", on_delete_event)
            self.progress_bar_win.connect("destroy", self.on_destroy_progress_bar_win)

            GLib.idle_add(self.networks_queue_progress_update)

    def networks_queue_progress_update(self):
        if self.networks.queue_task is None:
            self.progress_bar_win.destroy()
            return False
        progress = 100 / self.progress_bar_max * (self.progress_bar_max - len(self.networks.notify_add_queue))
        self.progress_bar.set_text("%s%%, %s сетей осталось" % (round(progress, 1), len(self.networks.notify_add_queue)))
        self.progress_bar.set_fraction(progress / 100)
        return True

    def on_destroy_progress_bar_win(self, window):
        self.progress_bar_win = None

    def add_server_tab(self, server_id):
        self.server_tabs[server_id] = ServerTab(server_id, self.map, self.config, self.client_threads,
                                                self.client_start, self.client_stop, self.set_server_tab_label,
                                                self.on_server_remove_clicked, window=self.gtkwin, logger=self.logger)
        self.server_notebook.append_page(self.server_tabs[server_id].widget)
        self.server_tabs[server_id].set_active()

    def set_server_tab_label(self, server_id, icon, tooltip):
        table = self.get_server_tab_widget(server_id)
        hbox = Gtk.HBox()
        label = Gtk.Label()
        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_tooltip_text(tooltip)
        hbox.add(label)
        hbox.add(image)
        hbox.show_all()
        label.set_text("%s " % (server_id + 1))
        label.set_tooltip_text(tooltip)
        notebook = table.get_parent()
        notebook.set_tab_label(table, hbox)

    def get_server_tab_widget(self, server_id):
        return self.server_tabs[server_id].widget

    def on_server_remove_clicked(self, widget, server_id):
        if self.server_notebook.get_n_pages() == 1:
            # last connection
            dialog = Gtk.Dialog("Инфо")
            dialog.set_transient_for(self.gtkwin)
            label = Gtk.Label("Вы не можете удалить последнее соединение!")
            area = dialog.get_content_area()
            area.add(label)
            dialog.add_button('gtk-cancel', 1)
            dialog.show_all()
            dialog.run()
            dialog.destroy()
            return

        table = self.get_server_tab_widget(server_id)
        page_num = self.server_notebook.page_num(table)
        self.server_notebook.remove_page(page_num)
        self.client_stop(server_id)
        self.config['servers'][server_id] = None
        self.map.remove_track(server_id)
        self.map.remove_marker("сервер%s" % (server_id + 1))

    def on_add_server_clicked(self, widget):
        server_id = len(self.client_threads)
        self.logger.debug("добавление сервера %s" % (server_id + 1))
        self.config['servers'].append(
            {
                'uri': "http://server%s:2501" % (server_id + 1),
                'username': '',
                'password': '',
                'id': server_id
            }
        )
        self.client_start(server_id)
        self.add_server_tab(server_id)

    def on_map_hide(self, widget):
        self.config["window"]["map_position"] = "hide"

    def on_map_window(self, widget=None, override=False):
        if (widget is not None and widget.get_active()) or override is True:
            try:
                self.map_window.gtkwin.hide()
                self.map_window.gtkwin.show()
                return
            except:
                pass
            self.config["window"]["map_position"] = "window"
            self.map_window = MapWindow(self.map)
            self.map_window.gtkwin.show_all()
        else:
            try:
                self.map_window.gtkwin.destroy()
            except AttributeError:
                pass

    def on_map_widget(self, widget=None, override=False):
        map_widget = self.map.widget
        if (widget is not None and widget.get_active()) or override is True:
            if self.config["window"]["map_position"] == "widget" and self.notebook.page_num(map_widget) != -1:
                # виджет уже прикреплен
                return
            self.config["window"]["map_position"] = "widget"
            self.notebook.append_page(map_widget)
            page_num = self.notebook.page_num(map_widget)
            self.notebook.set_tab_label_text(map_widget, "Карта")
            map_widget.show_all()
            self.map.set_last_from_config()
            self.notebook.set_current_page(page_num)
        else:
            page = self.notebook.page_num(map_widget)
            if page >= 0:
                self.notebook.remove_page(page)

#    def on_about_dialog(self, widget):
#        dialog = Gtk.AboutDialog()
#        dialog.set_program_name("Монитор беспроводных устройств")
#        dialog.set_version(utils.get_version())
#        dialog.set_comments('GUI для kismet')
#        dialog.set_website('https://www.salecker.org/software/kismon.html')
#        dialog.set_copyright("(c) 2010-2019 Patrick Salecker")
#        dialog.run()
#        dialog.destroy()

    def on_window_state(self, window, event):
        if event.new_window_state == Gdk.WindowState.MAXIMIZED:
            self.config["window"]["maximized"] = True
        else:
            self.config["window"]["maximized"] = False

    def on_configure_event(self, widget, event):
        width, height = self.gtkwin.get_size()
        self.config["window"]["width"] = width
        self.config["window"]["height"] = height

    def on_config_window(self, widget):
        if self.config_window is not None:
            try:
                self.config_window.gtkwin.hide()
                self.config_window.gtkwin.show()
                return
            except:
                pass

        self.config_window = ConfigWindow(self)

    def on_signal_graph(self, widget):
        mac = self.network_list.network_selected
        signal_window = SignalWindow(mac, self.on_signal_graph_destroy, seconds=self.config['window']['signal_window_seconds'])
        self.signal_graphs[mac] = signal_window

    def on_signal_graph_destroy(self, window, mac):
        del self.signal_graphs[mac]

    def on_file_import(self, widget):
        file_import_window = FileImportWindow(self.networks, self.networks_queue_progress)
        file_import_window.gtkwin.set_transient_for(self.gtkwin)
        file_import_window.gtkwin.set_modal(True)

    def on_file_export(self, widget, export_format, extension, amount):
        dialog = Gtk.FileChooserDialog(title="Экспортировать как %s" % export_format,
                                       action=Gtk.FileChooserAction.SAVE)
        dialog.set_transient_for(self.gtkwin)
        dialog.add_button('gtk-save', Gtk.ResponseType.OK)
        dialog.add_button('gtk-cancel', Gtk.ResponseType.CANCEL)
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_name("kismon.%s" % extension)

        filename = False
        if dialog.run() == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
        dialog.destroy()
        if not filename:
            return

        if amount == "Отфильтровано":
            networks = []
            for mac in self.export_networks:
                if self.export_networks[mac] is True:
                    networks.append(mac)
            filtered = True
        else:
            networks = None
            filtered = False

        self.networks.export_networks(export_format, filename, networks, self.tracks, filtered)

    def export_add_network(self, mac):
        self.export_networks[mac] = True

    def export_remove_network(self, mac):
        self.export_networks[mac] = False

    def update_statusbar(self):
        if self.map is not None:
            on_map = len(self.map.markers)
        else:
            on_map = 0

        text = "Сети: %s в текущем сеансе, %s всего, %s в списке сетей, %s на карте" % \
               (len(self.networks.recent_networks), len(self.networks.networks), len(self.network_list.network_iter),
                on_map)
        self.statusbar.push(self.statusbar_context, text)


if __name__ == "__main__":
    import kismet.core as core

    core.main()
