#
# gtkui.py
#
# Copyright (C) 2008 Andrew Resch <andrewresch@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#
#

import logging
from datetime import datetime
import gtk
import gtk.glade

from deluge.ui.client import client
import deluge.component as component
import deluge.common
from deluge.plugins.pluginbase import GtkPluginBase
import common

log = logging.getLogger(__name__)

class GtkUI(GtkPluginBase):
    def enable(self):
        log.debug("Blocklist GtkUI enable..")
        self.plugin = component.get("PluginManager")

        try:
            self.load_preferences_page()
        except Exception, err:
            log.exception(err)
            raise

        self.status_item = component.get("StatusBar").add_item(
            image=common.get_resource("blocklist16.png"),
            text="",
            callback=self._on_status_item_clicked,
            tooltip=_("Blocked IP Ranges /Whitelisted IP Ranges")
        )

        # Register some hooks
        self.plugin.register_hook("on_apply_prefs", self._on_apply_prefs)
        self.plugin.register_hook("on_show_prefs", self._on_show_prefs)

    def disable(self):
        log.debug("Blocklist GtkUI disable..")

        # Remove the preferences page
        self.plugin.remove_preferences_page(_("Blocklist"))

        # Remove status item
        component.get("StatusBar").remove_item(self.status_item)
        del self.status_item

        # Deregister the hooks
        self.plugin.deregister_hook("on_apply_prefs", self._on_apply_prefs)
        self.plugin.deregister_hook("on_show_prefs", self._on_show_prefs)

        del self.glade

    def update(self):
        def _on_get_status(status):
            if status["state"] == "Downloading":
                self.table_info.hide()
                self.glade.get_widget("button_check_download").set_sensitive(False)
                self.glade.get_widget("button_force_download").set_sensitive(False)
                self.glade.get_widget("image_up_to_date").hide()

                self.status_item.set_text(
                    "Downloading %.2f%%" % (status["file_progress"] * 100))
                self.progress_bar.set_text("Downloading %.2f%%" % (status["file_progress"] * 100))
                self.progress_bar.set_fraction(status["file_progress"])
                self.progress_bar.show()

            elif status["state"] == "Importing":
                self.table_info.hide()
                self.glade.get_widget("button_check_download").set_sensitive(False)
                self.glade.get_widget("button_force_download").set_sensitive(False)
                self.glade.get_widget("image_up_to_date").hide()

                self.status_item.set_text(
                    "Importing " + str(status["num_blocked"]))
                self.progress_bar.set_text("Importing %s" % (status["num_blocked"]))
                self.progress_bar.pulse()
                self.progress_bar.show()

            elif status["state"] == "Idle":
                self.progress_bar.hide()
                self.glade.get_widget("button_check_download").set_sensitive(True)
                self.glade.get_widget("button_force_download").set_sensitive(True)
                if status["up_to_date"]:
                    self.glade.get_widget("image_up_to_date").show()
                else:
                    self.glade.get_widget("image_up_to_date").hide()

                self.table_info.show()
                self.status_item.set_text("%(num_blocked)s/%(num_whited)s" % status)

                self.glade.get_widget("label_filesize").set_text(
                    deluge.common.fsize(status["file_size"]))
                self.glade.get_widget("label_modified").set_text(
                    datetime.fromtimestamp(status["file_date"]).strftime("%c"))
                self.glade.get_widget("label_type").set_text(status["file_type"])
                self.glade.get_widget("label_url").set_text(
                    status["file_url"])

        client.blocklist.get_status().addCallback(_on_get_status)

    def _on_show_prefs(self):
        def _on_get_config(config):
            log.trace("Loaded config: %s", config)
            self.glade.get_widget("entry_url").set_text(config["url"])
            self.glade.get_widget("spin_check_days").set_value(config["check_after_days"])
            self.glade.get_widget("chk_import_on_start").set_active(config["load_on_start"])
            self.populate_whitelist(config["whitelisted"])

        client.blocklist.get_config().addCallback(_on_get_config)

    def _on_apply_prefs(self):
        config = {}
        config["url"] = self.glade.get_widget("entry_url").get_text()
        config["check_after_days"] = self.glade.get_widget("spin_check_days").get_value_as_int()
        config["load_on_start"] = self.glade.get_widget("chk_import_on_start").get_active()
        config["whitelisted"] = [ip[0] for ip in self.whitelist_model if ip[0]!='IP HERE']
        client.blocklist.set_config(config)

    def _on_button_check_download_clicked(self, widget):
        self._on_apply_prefs()
        client.blocklist.check_import()

    def _on_button_force_download_clicked(self, widget):
        self._on_apply_prefs()
        client.blocklist.check_import(force=True)

    def _on_status_item_clicked(self, widget, event):
        component.get("Preferences").show(_("Blocklist"))

    def load_preferences_page(self):
        """Initializes the preferences page and adds it to the preferences dialog"""
        # Load the preferences page
        self.glade = gtk.glade.XML(common.get_resource("blocklist_pref.glade"))

        self.whitelist_frame = self.glade.get_widget("whitelist_frame")
        self.progress_bar = self.glade.get_widget("progressbar")
        self.table_info = self.glade.get_widget("table_info")

        # Hide the progress bar initially
        self.progress_bar.hide()
        self.table_info.show()

        # Create the whitelisted model
        self.build_whitelist_model_treeview()

        self.glade.signal_autoconnect({
            "on_button_check_download_clicked": self._on_button_check_download_clicked,
            "on_button_force_download_clicked": self._on_button_force_download_clicked,
            'on_whitelist_add_clicked': (self.on_add_button_clicked,
                                         self.whitelist_treeview),
            'on_whitelist_remove_clicked': (self.on_delete_button_clicked,
                                            self.whitelist_treeview),
        })

        # Set button icons
        self.glade.get_widget("image_download").set_from_file(
            common.get_resource("blocklist_download24.png"))

        self.glade.get_widget("image_import").set_from_file(
            common.get_resource("blocklist_import24.png"))

        # Update the preferences page with config values from the core
        self._on_show_prefs()

        # Add the page to the preferences dialog
        self.plugin.add_preferences_page(
            _("Blocklist"),
            self.glade.get_widget("blocklist_prefs_box"))

    def build_whitelist_model_treeview(self):
        self.whitelist_treeview = self.glade.get_widget("whitelist_treeview")
        treeview_selection = self.whitelist_treeview.get_selection()
        treeview_selection.connect(
            "changed", self.on_whitelist_treeview_selection_changed
        )
        self.whitelist_model = gtk.ListStore(str, bool)
        renderer = gtk.CellRendererText()
        renderer.connect("edited", self.on_cell_edited, self.whitelist_model)
        renderer.set_data("ip", 0)

        column = gtk.TreeViewColumn("IPs", renderer, text=0, editable=1)
        column.set_expand(True)
        self.whitelist_treeview.append_column(column)
        self.whitelist_treeview.set_model(self.whitelist_model)

    def on_cell_edited(self, cell, path_string, new_text, model):
#        iter = model.get_iter_from_string(path_string)
#        path = model.get_path(iter)[0]
        try:
            ip = common.IP.parse(new_text)
            model.set(model.get_iter_from_string(path_string), 0, ip.address)
        except common.BadIP, e:
            model.remove(model.get_iter_from_string(path_string))
            from deluge.ui.gtkui import dialogs
            d = dialogs.ErrorDialog(_("Bad IP address"), e.message)
            d.run()


    def on_whitelist_treeview_selection_changed(self, selection):
        model, selected_connection_iter = selection.get_selected()
        if selected_connection_iter:
            self.glade.get_widget("whitelist_delete").set_property('sensitive',
                                                                   True)
        else:
            self.glade.get_widget("whitelist_delete").set_property('sensitive',
                                                                   False)

    def on_add_button_clicked(self, widget, treeview):
        model = treeview.get_model()
        model.set(model.append(), 0, "IP HERE", 1, True)

    def on_delete_button_clicked(self, widget, treeview):
        selection = treeview.get_selection()
        model, iter = selection.get_selected()
        if iter:
#            path = model.get_path(iter)[0]
            model.remove(iter)

    def populate_whitelist(self, whitelist):
        self.whitelist_model.clear()
        for ip in whitelist:
            self.whitelist_model.set(
                self.whitelist_model.append(),0, ip, 1, True
            )
