"""
Main Debai GTK4/Adwaita Application.

A modern, accessible GUI for managing AI agents.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from debai import __version__
from debai.core.agent import AgentManager, AgentConfig, AgentType, get_agent_template, list_agent_templates
from debai.core.model import ModelManager, ModelConfig, get_recommended_model, list_recommended_models
from debai.core.task import TaskManager, TaskConfig
from debai.core.system import SystemInfo, ResourceMonitor, check_dependencies

logger = logging.getLogger(__name__)


class DebaiApplication(Adw.Application):
    """Main Debai Application."""
    
    def __init__(self):
        super().__init__(
            application_id="org.debai.Debai",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        
        self.window: Optional[DebaiWindow] = None
        self.agent_manager = AgentManager()
        self.model_manager = ModelManager()
        self.task_manager = TaskManager()
        self.resource_monitor = ResourceMonitor()
        
        # Load existing data
        self.agent_manager.load_agents()
        self.model_manager.load_models()
        self.task_manager.load_tasks()
    
    def do_activate(self):
        """Called when the application is activated."""
        if not self.window:
            self.window = DebaiWindow(application=self)
        self.window.present()
    
    def do_startup(self):
        """Called when the application starts."""
        Adw.Application.do_startup(self)
        
        # Set up actions
        self._setup_actions()
        
        # Apply CSS
        self._load_css()
    
    def _setup_actions(self):
        """Set up application actions."""
        actions = [
            ("quit", self.on_quit),
            ("about", self.on_about),
            ("preferences", self.on_preferences),
            ("new-agent", self.on_new_agent),
            ("new-task", self.on_new_task),
        ]
        
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        
        # Keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.new-agent", ["<Control>n"])
        self.set_accels_for_action("app.preferences", ["<Control>comma"])
    
    def _load_css(self):
        """Load custom CSS styles."""
        css = """
        .agent-card {
            padding: 12px;
            border-radius: 12px;
            background: alpha(@card_bg_color, 0.8);
        }
        
        .agent-card:hover {
            background: @card_bg_color;
        }
        
        .status-running {
            color: #2ec27e;
        }
        
        .status-stopped {
            color: #77767b;
        }
        
        .status-error {
            color: #e01b24;
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: bold;
        }
        
        .metric-label {
            font-size: 0.9em;
            color: @dim_label_color;
        }
        
        .sidebar-header {
            padding: 12px;
            font-weight: bold;
        }
        
        .welcome-title {
            font-size: 2em;
            font-weight: bold;
        }
        
        .chat-user {
            background: alpha(@accent_bg_color, 0.2);
            border-radius: 12px;
            padding: 8px 12px;
            margin: 4px 48px 4px 12px;
        }
        
        .chat-assistant {
            background: alpha(@card_bg_color, 0.8);
            border-radius: 12px;
            padding: 8px 12px;
            margin: 4px 12px 4px 48px;
        }
        """
        
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        
        # Get display from window or default display
        if self.window:
            display = self.window.get_display()
        else:
            display = Gdk.Display.get_default()
        
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
    
    def on_quit(self, action, param):
        """Handle quit action."""
        self.quit()
    
    def on_about(self, action, param):
        """Show about dialog."""
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name="Debai",
            application_icon="application-x-executable",
            developer_name="Debai Team",
            version=__version__,
            copyright="© 2025 Debai Team",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/manalejandro/debai",
            issue_url="https://github.com/manalejandro/debai/issues",
            comments="AI Agent Management System for GNU/Linux",
            developers=["Debai Team"],
        )
        about.add_acknowledgement_section(
            "Powered by",
            ["Docker Model Runner", "cagent", "GTK4", "Adwaita"],
        )
        about.present()
    
    def on_preferences(self, action, param):
        """Show preferences dialog."""
        dialog = PreferencesDialog(transient_for=self.window)
        dialog.present()
    
    def on_new_agent(self, action, param):
        """Show new agent dialog."""
        if self.window:
            self.window.show_new_agent_dialog()
    
    def on_new_task(self, action, param):
        """Show new task dialog."""
        if self.window:
            self.window.show_new_task_dialog()


class DebaiWindow(Adw.ApplicationWindow):
    """Main application window."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Debai")
        self.set_default_size(1400, 900)
        
        # Main layout
        self._build_ui()
        
        # Start resource monitoring
        self._start_monitoring()
    
    def _build_ui(self):
        """Build the main UI."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        
        # Header bar
        header = Adw.HeaderBar()
        
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._create_app_menu())
        header.pack_end(menu_button)
        
        # New button
        new_button = Gtk.Button()
        new_button.set_icon_name("list-add-symbolic")
        new_button.set_tooltip_text("Create new agent")
        new_button.connect("clicked", lambda b: self.show_new_agent_dialog())
        header.pack_start(new_button)
        
        main_box.append(header)
        
        # Navigation view
        self.nav_view = Adw.NavigationView()
        self.nav_view.set_vexpand(True)
        self.nav_view.set_hexpand(True)
        main_box.append(self.nav_view)
        
        # Main page with sidebar
        main_page = Adw.NavigationPage(title="Debai")
        self.nav_view.push(main_page)
        
        # Split view
        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(250)
        split_view.set_max_sidebar_width(350)
        main_page.set_child(split_view)
        
        # Sidebar
        sidebar = self._create_sidebar()
        split_view.set_sidebar(sidebar)
        
        # Content area
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_vexpand(True)
        self.content_stack.set_hexpand(True)
        
        # Add content pages
        self.content_stack.add_named(self._create_dashboard_page(), "dashboard")
        self.content_stack.add_named(self._create_agents_page(), "agents")
        self.content_stack.add_named(self._create_models_page(), "models")
        self.content_stack.add_named(self._create_tasks_page(), "tasks")
        self.content_stack.add_named(self._create_generate_page(), "generate")
        
        content_page = Adw.NavigationPage(title="Dashboard")
        content_page.set_child(self.content_stack)
        split_view.set_content(content_page)
    
    def _create_app_menu(self) -> Gio.Menu:
        """Create the application menu."""
        menu = Gio.Menu()
        
        menu.append("Preferences", "app.preferences")
        menu.append("Keyboard Shortcuts", "win.show-help-overlay")
        menu.append("About Debai", "app.about")
        menu.append("Quit", "app.quit")
        
        return menu
    
    def _create_sidebar(self) -> Adw.NavigationPage:
        """Create the sidebar navigation."""
        sidebar_page = Adw.NavigationPage(title="Navigation")
        
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_page.set_child(sidebar_box)
        
        # Sidebar header
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_end_title_buttons(False)
        sidebar_box.append(sidebar_header)
        
        # Navigation list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        sidebar_box.append(scrolled)
        
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.add_css_class("navigation-sidebar")
        scrolled.set_child(listbox)
        
        # Navigation items
        nav_items = [
            ("dashboard", "view-grid-symbolic", "Dashboard"),
            ("agents", "system-users-symbolic", "Agents"),
            ("models", "applications-science-symbolic", "Models"),
            ("tasks", "view-list-symbolic", "Tasks"),
            ("generate", "drive-optical-symbolic", "Generate"),
        ]
        
        for page_id, icon, label in nav_items:
            row = Adw.ActionRow(title=label)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))
            row.set_activatable(True)
            row.page_id = page_id
            listbox.append(row)
        
        listbox.connect("row-activated", self._on_nav_row_activated)
        
        # Select first row
        listbox.select_row(listbox.get_row_at_index(0))
        
        return sidebar_page
    
    def _on_nav_row_activated(self, listbox, row):
        """Handle navigation row activation."""
        if hasattr(row, "page_id"):
            self.content_stack.set_visible_child_name(row.page_id)
    
    def _create_dashboard_page(self) -> Gtk.Widget:
        """Create the dashboard page."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(24)
        page.set_margin_bottom(24)
        scrolled.set_child(page)
        
        # Welcome section
        welcome_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        welcome_label = Gtk.Label(label="Welcome to Debai")
        welcome_label.add_css_class("welcome-title")
        welcome_label.set_halign(Gtk.Align.START)
        welcome_box.append(welcome_label)
        
        subtitle_label = Gtk.Label(label="AI Agent Management System for GNU/Linux")
        subtitle_label.add_css_class("dim-label")
        subtitle_label.set_halign(Gtk.Align.START)
        welcome_box.append(subtitle_label)
        
        page.append(welcome_box)
        
        # System metrics
        metrics_label = Gtk.Label(label="System Status")
        metrics_label.add_css_class("heading")
        metrics_label.set_halign(Gtk.Align.START)
        page.append(metrics_label)
        
        metrics_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        metrics_box.set_homogeneous(True)
        
        # CPU metric
        self.cpu_metric = self._create_metric_card("CPU", "0%", "processor-symbolic")
        metrics_box.append(self.cpu_metric)
        
        # Memory metric
        self.memory_metric = self._create_metric_card("Memory", "0%", "drive-harddisk-symbolic")
        metrics_box.append(self.memory_metric)
        
        # Agents metric
        app = self.get_application()
        agent_count = len(app.agent_manager.list_agents()) if app else 0
        self.agents_metric = self._create_metric_card("Agents", str(agent_count), "system-users-symbolic")
        metrics_box.append(self.agents_metric)
        
        # Tasks metric
        task_count = len(app.task_manager.list_tasks()) if app else 0
        self.tasks_metric = self._create_metric_card("Tasks", str(task_count), "view-list-symbolic")
        metrics_box.append(self.tasks_metric)
        
        page.append(metrics_box)
        
        # Quick actions
        actions_label = Gtk.Label(label="Quick Actions")
        actions_label.add_css_class("heading")
        actions_label.set_halign(Gtk.Align.START)
        page.append(actions_label)
        
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        create_agent_btn = Gtk.Button(label="Create Agent")
        create_agent_btn.add_css_class("suggested-action")
        create_agent_btn.add_css_class("pill")
        create_agent_btn.connect("clicked", lambda b: self.show_new_agent_dialog())
        actions_box.append(create_agent_btn)
        
        pull_model_btn = Gtk.Button(label="Pull Model")
        pull_model_btn.add_css_class("pill")
        pull_model_btn.connect("clicked", lambda b: self.show_pull_model_dialog())
        actions_box.append(pull_model_btn)
        
        create_task_btn = Gtk.Button(label="Create Task")
        create_task_btn.add_css_class("pill")
        create_task_btn.connect("clicked", lambda b: self.show_new_task_dialog())
        actions_box.append(create_task_btn)
        
        page.append(actions_box)
        
        # Dependencies status
        deps_label = Gtk.Label(label="Dependencies")
        deps_label.add_css_class("heading")
        deps_label.set_halign(Gtk.Align.START)
        page.append(deps_label)
        
        deps_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        deps = check_dependencies()
        
        for dep, available in deps.items():
            chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            chip.add_css_class("card")
            chip.set_margin_top(4)
            chip.set_margin_bottom(4)
            chip.set_margin_start(4)
            chip.set_margin_end(4)
            
            icon = Gtk.Image.new_from_icon_name(
                "emblem-ok-symbolic" if available else "dialog-error-symbolic"
            )
            icon.add_css_class("status-running" if available else "status-error")
            chip.append(icon)
            
            label = Gtk.Label(label=dep)
            chip.append(label)
            
            deps_box.append(chip)
        
        page.append(deps_box)
        
        # Scrollable
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(page)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        return scrolled
    
    def _create_metric_card(self, label: str, value: str, icon: str) -> Gtk.Widget:
        """Create a metric card widget."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("card")
        card.set_margin_top(16)
        card.set_margin_bottom(16)
        card.set_margin_start(16)
        card.set_margin_end(16)
        
        icon_widget = Gtk.Image.new_from_icon_name(icon)
        icon_widget.set_pixel_size(32)
        icon_widget.add_css_class("dim-label")
        card.append(icon_widget)
        
        value_label = Gtk.Label(label=value)
        value_label.add_css_class("metric-value")
        value_label.set_name(f"metric-{label.lower()}-value")
        card.append(value_label)
        
        name_label = Gtk.Label(label=label)
        name_label.add_css_class("metric-label")
        card.append(name_label)
        
        return card
    
    def _create_agents_page(self) -> Gtk.Widget:
        """Create the agents page."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.set_vexpand(True)
        page.set_hexpand(True)
        
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_start(16)
        toolbar.set_margin_end(16)
        toolbar.set_margin_top(16)
        toolbar.set_margin_bottom(8)
        
        title = Gtk.Label(label="AI Agents")
        title.add_css_class("title-2")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)
        
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh")
        refresh_btn.connect("clicked", lambda b: self._refresh_agents())
        toolbar.append(refresh_btn)
        
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_btn.add_css_class("suggested-action")
        add_btn.set_tooltip_text("Create agent")
        add_btn.connect("clicked", lambda b: self.show_new_agent_dialog())
        toolbar.append(add_btn)
        
        page.append(toolbar)
        
        # Agent list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.agents_list = Gtk.ListBox()
        self.agents_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.agents_list.add_css_class("boxed-list")
        self.agents_list.set_margin_start(16)
        self.agents_list.set_margin_end(16)
        self.agents_list.set_margin_bottom(16)
        
        scrolled.set_child(self.agents_list)
        page.append(scrolled)
        
        # Populate agents
        self._refresh_agents()
        
        return page
    
    def _refresh_agents(self):
        """Refresh the agents list."""
        # Clear existing
        while True:
            row = self.agents_list.get_row_at_index(0)
            if row is None:
                break
            self.agents_list.remove(row)
        
        app = self.get_application()
        if not app:
            return
        
        agents = app.agent_manager.list_agents()
        
        if not agents:
            # Empty state
            empty = Adw.StatusPage(
                title="No Agents",
                description="Create your first AI agent to get started",
                icon_name="system-users-symbolic",
            )
            empty_btn = Gtk.Button(label="Create Agent")
            empty_btn.add_css_class("suggested-action")
            empty_btn.add_css_class("pill")
            empty_btn.set_halign(Gtk.Align.CENTER)
            empty_btn.connect("clicked", lambda b: self.show_new_agent_dialog())
            empty.set_child(empty_btn)
            
            self.agents_list.append(empty)
            return
        
        for agent in agents:
            row = self._create_agent_row(agent)
            self.agents_list.append(row)
    
    def _create_agent_row(self, agent) -> Gtk.Widget:
        """Create an agent list row."""
        row = Adw.ActionRow()
        row.set_title(agent.name)
        row.set_subtitle(f"{agent.config.agent_type} • {agent.config.model_id}")
        
        # Status icon
        status_class = {
            "running": "status-running",
            "stopped": "status-stopped",
            "error": "status-error",
        }.get(agent.status.value, "status-stopped")
        
        status_icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
        status_icon.add_css_class(status_class)
        row.add_prefix(status_icon)
        
        # Actions
        if agent.status.value == "running":
            stop_btn = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic")
            stop_btn.set_tooltip_text("Stop agent")
            stop_btn.set_valign(Gtk.Align.CENTER)
            stop_btn.add_css_class("flat")
            row.add_suffix(stop_btn)
            
            chat_btn = Gtk.Button.new_from_icon_name("user-available-symbolic")
            chat_btn.set_tooltip_text("Chat with agent")
            chat_btn.set_valign(Gtk.Align.CENTER)
            chat_btn.add_css_class("flat")
            row.add_suffix(chat_btn)
        else:
            start_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
            start_btn.set_tooltip_text("Start agent")
            start_btn.set_valign(Gtk.Align.CENTER)
            start_btn.add_css_class("flat")
            row.add_suffix(start_btn)
        
        delete_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        delete_btn.set_tooltip_text("Delete agent")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn.add_css_class("flat")
        delete_btn.add_css_class("error")
        row.add_suffix(delete_btn)
        
        return row
    
    def _create_models_page(self) -> Gtk.Widget:
        """Create the models page."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.set_vexpand(True)
        page.set_hexpand(True)
        
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_start(16)
        toolbar.set_margin_end(16)
        toolbar.set_margin_top(16)
        toolbar.set_margin_bottom(8)
        
        title = Gtk.Label(label="AI Models")
        title.add_css_class("title-2")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)
        
        pull_btn = Gtk.Button(label="Pull Model")
        pull_btn.add_css_class("suggested-action")
        pull_btn.connect("clicked", lambda b: self.show_pull_model_dialog())
        toolbar.append(pull_btn)
        
        page.append(toolbar)
        
        # Model list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.models_list = Gtk.ListBox()
        self.models_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.models_list.add_css_class("boxed-list")
        self.models_list.set_margin_start(16)
        self.models_list.set_margin_end(16)
        self.models_list.set_margin_bottom(16)
        
        scrolled.set_child(self.models_list)
        page.append(scrolled)
        
        # Populate with recommended models
        for name in list_recommended_models():
            config = get_recommended_model(name)
            if config:
                row = Adw.ActionRow()
                row.set_title(config.name)
                row.set_subtitle(config.description)
                
                size_label = Gtk.Label(label=config.parameter_count)
                size_label.add_css_class("dim-label")
                row.add_suffix(size_label)
                
                pull_btn = Gtk.Button(label="Pull")
                pull_btn.set_valign(Gtk.Align.CENTER)
                pull_btn.add_css_class("pill")
                row.add_suffix(pull_btn)
                
                self.models_list.append(row)
        
        return page
    
    def _create_tasks_page(self) -> Gtk.Widget:
        """Create the tasks page."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.set_vexpand(True)
        page.set_hexpand(True)
        
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_start(16)
        toolbar.set_margin_end(16)
        toolbar.set_margin_top(16)
        toolbar.set_margin_bottom(8)
        
        title = Gtk.Label(label="Automated Tasks")
        title.add_css_class("title-2")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        toolbar.append(title)
        
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_btn.add_css_class("suggested-action")
        add_btn.set_tooltip_text("Create task")
        add_btn.connect("clicked", lambda b: self.show_new_task_dialog())
        toolbar.append(add_btn)
        
        page.append(toolbar)
        
        # Task list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        tasks_list = Gtk.ListBox()
        tasks_list.set_selection_mode(Gtk.SelectionMode.NONE)
        tasks_list.add_css_class("boxed-list")
        tasks_list.set_margin_start(16)
        tasks_list.set_margin_end(16)
        tasks_list.set_margin_bottom(16)
        
        # Add sample tasks
        from debai.core.task import list_task_templates, get_task_template
        
        for name in list_task_templates():
            config = get_task_template(name)
            if config:
                row = Adw.ActionRow()
                row.set_title(config.name)
                row.set_subtitle(config.description)
                
                priority_label = Gtk.Label(label=config.priority.upper())
                priority_label.add_css_class("dim-label")
                row.add_suffix(priority_label)
                
                run_btn = Gtk.Button(label="Run")
                run_btn.set_valign(Gtk.Align.CENTER)
                run_btn.add_css_class("pill")
                row.add_suffix(run_btn)
                
                tasks_list.append(row)
        
        scrolled.set_child(tasks_list)
        page.append(scrolled)
        
        return page
    
    def _create_generate_page(self) -> Gtk.Widget:
        """Create the generate page."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.set_margin_start(24)
        page.set_margin_end(24)
        page.set_margin_top(24)
        page.set_margin_bottom(24)
        scrolled.set_child(page)
        
        title = Gtk.Label(label="Generate Distribution")
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        page.append(title)
        
        subtitle = Gtk.Label(
            label="Create deployable images with Debai pre-installed"
        )
        subtitle.add_css_class("dim-label")
        subtitle.set_halign(Gtk.Align.START)
        page.append(subtitle)
        
        # Options
        options_group = Adw.PreferencesGroup(title="Output Format")
        
        # ISO option
        iso_row = Adw.ActionRow(
            title="ISO Image",
            subtitle="Bootable ISO for installation or live boot",
        )
        iso_row.add_prefix(Gtk.Image.new_from_icon_name("drive-optical-symbolic"))
        iso_btn = Gtk.Button(label="Generate")
        iso_btn.set_valign(Gtk.Align.CENTER)
        iso_btn.add_css_class("pill")
        iso_row.add_suffix(iso_btn)
        options_group.add(iso_row)
        
        # QCOW2 option
        qcow2_row = Adw.ActionRow(
            title="QCOW2 Image",
            subtitle="Virtual machine disk for QEMU/KVM",
        )
        qcow2_row.add_prefix(Gtk.Image.new_from_icon_name("drive-harddisk-symbolic"))
        qcow2_btn = Gtk.Button(label="Generate")
        qcow2_btn.set_valign(Gtk.Align.CENTER)
        qcow2_btn.add_css_class("pill")
        qcow2_row.add_suffix(qcow2_btn)
        options_group.add(qcow2_row)
        
        # Docker Compose option
        compose_row = Adw.ActionRow(
            title="Docker Compose",
            subtitle="Container orchestration configuration",
        )
        compose_row.add_prefix(Gtk.Image.new_from_icon_name("application-x-executable-symbolic"))
        compose_btn = Gtk.Button(label="Generate")
        compose_btn.set_valign(Gtk.Align.CENTER)
        compose_btn.add_css_class("pill")
        compose_row.add_suffix(compose_btn)
        options_group.add(compose_row)
        
        page.append(options_group)
        
        return scrolled
    
    def _start_monitoring(self):
        """Start resource monitoring in background."""
        def update_metrics():
            info = SystemInfo.get_cpu_info()
            mem = SystemInfo.get_memory_info()
            
            # Update CPU
            cpu_card = self.cpu_metric
            for child in cpu_card:
                if isinstance(child, Gtk.Label) and "metric-value" in child.get_css_classes():
                    child.set_label(f"{info.usage_percent:.0f}%")
            
            # Update Memory
            mem_card = self.memory_metric
            for child in mem_card:
                if isinstance(child, Gtk.Label) and "metric-value" in child.get_css_classes():
                    child.set_label(f"{mem.percent_used:.0f}%")
            
            return True
        
        GLib.timeout_add_seconds(2, update_metrics)
    
    def show_new_agent_dialog(self):
        """Show dialog to create a new agent."""
        dialog = NewAgentDialog(transient_for=self)
        dialog.present()
    
    def show_new_task_dialog(self):
        """Show dialog to create a new task."""
        dialog = NewTaskDialog(transient_for=self)
        dialog.present()
    
    def show_pull_model_dialog(self):
        """Show dialog to pull a model."""
        dialog = PullModelDialog(transient_for=self)
        dialog.present()


class NewAgentDialog(Adw.Window):
    """Dialog for creating a new agent."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Create Agent")
        self.set_default_size(500, 600)
        self.set_modal(True)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog UI."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)
        
        # Header
        header = Adw.HeaderBar()
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        header.pack_start(cancel_btn)
        
        create_btn = Gtk.Button(label="Create")
        create_btn.add_css_class("suggested-action")
        create_btn.connect("clicked", self._on_create)
        header.pack_end(create_btn)
        
        box.append(header)
        
        # Content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        box.append(scrolled)
        
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        scrolled.set_child(content)
        
        # Basic info
        basic_group = Adw.PreferencesGroup(title="Basic Information")
        
        self.name_entry = Adw.EntryRow(title="Name")
        basic_group.add(self.name_entry)
        
        self.desc_entry = Adw.EntryRow(title="Description")
        basic_group.add(self.desc_entry)
        
        content.append(basic_group)
        
        # Type selection
        type_group = Adw.PreferencesGroup(title="Agent Type")
        
        self.type_combo = Adw.ComboRow(title="Type")
        type_model = Gtk.StringList()
        for t in AgentType:
            type_model.append(t.value)
        self.type_combo.set_model(type_model)
        type_group.add(self.type_combo)
        
        content.append(type_group)
        
        # Model selection
        model_group = Adw.PreferencesGroup(title="AI Model")
        
        self.model_combo = Adw.ComboRow(title="Model")
        model_list = Gtk.StringList()
        for name in list_recommended_models():
            config = get_recommended_model(name)
            if config:
                model_list.append(config.id)
        self.model_combo.set_model(model_list)
        model_group.add(self.model_combo)
        
        content.append(model_group)
        
        # Options
        options_group = Adw.PreferencesGroup(title="Options")
        
        self.interactive_switch = Adw.SwitchRow(
            title="Interactive",
            subtitle="Allow user interaction with the agent",
        )
        self.interactive_switch.set_active(True)
        options_group.add(self.interactive_switch)
        
        self.autostart_switch = Adw.SwitchRow(
            title="Auto-start",
            subtitle="Start agent automatically on system boot",
        )
        options_group.add(self.autostart_switch)
        
        content.append(options_group)
        
        # Templates
        templates_group = Adw.PreferencesGroup(title="Templates")
        templates_group.set_description("Or choose from a predefined template")
        
        for name in list_agent_templates():
            template = get_agent_template(name)
            if template:
                row = Adw.ActionRow(
                    title=template.name,
                    subtitle=template.description,
                )
                use_btn = Gtk.Button(label="Use")
                use_btn.set_valign(Gtk.Align.CENTER)
                use_btn.add_css_class("pill")
                use_btn.template_name = name
                use_btn.connect("clicked", self._on_use_template)
                row.add_suffix(use_btn)
                templates_group.add(row)
        
        content.append(templates_group)
    
    def _on_use_template(self, button):
        """Apply a template."""
        template = get_agent_template(button.template_name)
        if template:
            self.name_entry.set_text(template.name)
            self.desc_entry.set_text(template.description)
            # Set other fields based on template
    
    def _on_create(self, button):
        """Create the agent."""
        # TODO: Implement agent creation
        self.close()


class NewTaskDialog(Adw.Window):
    """Dialog for creating a new task."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Create Task")
        self.set_default_size(500, 500)
        self.set_modal(True)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog UI."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)
        
        # Header
        header = Adw.HeaderBar()
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        header.pack_start(cancel_btn)
        
        create_btn = Gtk.Button(label="Create")
        create_btn.add_css_class("suggested-action")
        header.pack_end(create_btn)
        
        box.append(header)
        
        # Content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        box.append(content)
        
        # Basic info
        basic_group = Adw.PreferencesGroup(title="Task Information")
        
        name_entry = Adw.EntryRow(title="Name")
        basic_group.add(name_entry)
        
        command_entry = Adw.EntryRow(title="Command")
        basic_group.add(command_entry)
        
        content.append(basic_group)


class PullModelDialog(Adw.Window):
    """Dialog for pulling a model."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Pull Model")
        self.set_default_size(500, 400)
        self.set_modal(True)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog UI."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)
        
        # Header
        header = Adw.HeaderBar()
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        header.pack_start(cancel_btn)
        
        pull_btn = Gtk.Button(label="Pull")
        pull_btn.add_css_class("suggested-action")
        header.pack_end(pull_btn)
        
        box.append(header)
        
        # Content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        box.append(content)
        
        # Model ID entry
        model_group = Adw.PreferencesGroup(title="Model")
        
        model_entry = Adw.EntryRow(title="Model ID")
        model_entry.set_text("llama3.2:3b")
        model_group.add(model_entry)
        
        content.append(model_group)
        
        # Recommended models
        recommended_group = Adw.PreferencesGroup(title="Recommended Models")
        
        for name in list_recommended_models():
            config = get_recommended_model(name)
            if config:
                row = Adw.ActionRow(
                    title=config.id,
                    subtitle=f"{config.description} ({config.parameter_count})",
                )
                select_btn = Gtk.Button.new_from_icon_name("object-select-symbolic")
                select_btn.set_valign(Gtk.Align.CENTER)
                select_btn.add_css_class("flat")
                row.add_suffix(select_btn)
                recommended_group.add(row)
        
        content.append(recommended_group)


class PreferencesDialog(Adw.PreferencesWindow):
    """Preferences dialog."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Preferences")
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the preferences UI."""
        # General page
        general_page = Adw.PreferencesPage(
            title="General",
            icon_name="preferences-system-symbolic",
        )
        self.add(general_page)
        
        # Appearance group
        appearance_group = Adw.PreferencesGroup(title="Appearance")
        
        dark_mode = Adw.SwitchRow(
            title="Dark Mode",
            subtitle="Use dark color scheme",
        )
        appearance_group.add(dark_mode)
        
        general_page.add(appearance_group)
        
        # Behavior group
        behavior_group = Adw.PreferencesGroup(title="Behavior")
        
        auto_start = Adw.SwitchRow(
            title="Start on Login",
            subtitle="Start Debai when you log in",
        )
        behavior_group.add(auto_start)
        
        notifications = Adw.SwitchRow(
            title="Notifications",
            subtitle="Show notifications for agent events",
        )
        notifications.set_active(True)
        behavior_group.add(notifications)
        
        general_page.add(behavior_group)
        
        # Models page
        models_page = Adw.PreferencesPage(
            title="Models",
            icon_name="applications-science-symbolic",
        )
        self.add(models_page)
        
        # Model settings
        model_group = Adw.PreferencesGroup(title="Default Model")
        
        default_model = Adw.ComboRow(title="Model")
        model_list = Gtk.StringList()
        for name in list_recommended_models():
            config = get_recommended_model(name)
            if config:
                model_list.append(config.id)
        default_model.set_model(model_list)
        model_group.add(default_model)
        
        models_page.add(model_group)
