from shiny import App, reactive, render, ui, Session
from typing import Any
import json
import base64
import urllib3
from pathlib import Path
import os

# Initialize http
http = urllib3.PoolManager()

# Task list names
TASK_LISTS = [
    "Personal", "Work", "Shopping", "Health",
    "Learning", "Projects", "Family", "Other"
]

app_ui = ui.page_fluid(
    ui.panel_title("Task Management System"),
    
    # GitHub Settings Card
    ui.card(
        ui.card_header("GitHub Settings"),
        ui.input_text("github_username", "GitHub Username", placeholder="Enter username"),
        ui.input_text("github_token", "GitHub Token", placeholder="Enter personal access token"),
        ui.input_text("github_repo", "Repository Name", placeholder="Enter repository name"),
        ui.input_action_button("save_settings", "Save Settings"),
        ui.input_action_button("load_settings", "Load Settings")
    ),
    
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_select(
                "selected_list",
                "Select Task List",
                choices=TASK_LISTS
            ),
            ui.input_text("task_name", "Task Name"),
            ui.input_text_area("task_description", "Task Description"),
            ui.input_action_button("add_task", "Add Task"),
            ui.input_action_button("update_task", "Update Selected Task"),
            ui.input_action_button("delete_task", "Delete Selected Task"),
            ui.tags.hr(),
            ui.input_select(
                "target_list",
                "Move Selected Tasks To:",
                choices=TASK_LISTS
            ),
            ui.input_action_button("move_tasks", "Move Tasks"),
            ui.tags.hr(),
            ui.input_action_button("save_current", "Save Current List"),
            ui.input_action_button("load_current", "Load Current List"),
            ui.tags.hr(),
            ui.input_action_button("save_all", "Save All Lists"),
            ui.input_action_button("load_all", "Load All Lists"),
        ),
        ui.card(
            ui.card_header("Tasks"),
            ui.output_ui("task_list"),
        ),
    )
)

def server(input: Any, output: Any, session: Session):
    # Reactive values for tasks and settings
    tasks = {list_name: reactive.value([]) for list_name in TASK_LISTS}
    selected_tasks = reactive.value(set())
    github_settings = reactive.value({})
    
    def get_github_file(filename):
        if not all(github_settings.get()):
            return None
        
        settings = github_settings.get()
        url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/contents/{filename}"
        headers = {
            "Authorization": f"token {settings['token']}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = http.request('GET', url, headers=headers)
        if response.status == 200:
            content = json.loads(response.data.decode('utf-8'))
            file_content = base64.b64decode(content['content']).decode('utf-8')
            return json.loads(file_content)
        return None

    def save_github_file(filename, content):
        if not all(github_settings.get()):
            return False
            
        settings = github_settings.get()
        url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/contents/{filename}"
        headers = {
            "Authorization": f"token {settings['token']}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Check if file exists
        response = http.request('GET', url, headers=headers)
        data = {
            "message": f"Update {filename}",
            "content": base64.b64encode(json.dumps(content).encode('utf-8')).decode('utf-8'),
        }
        
        if response.status == 200:
            current_file = json.loads(response.data.decode('utf-8'))
            data["sha"] = current_file["sha"]
        
        response = http.request(
            'PUT',
            url,
            headers=headers,
            body=json.dumps(data).encode('utf-8')
        )
        return response.status in (200, 201)

    @reactive.Effect
    @reactive.event(input.save_settings)
    def _():
        github_settings.set({
            "username": input.github_username(),
            "token": input.github_token(),
            "repo": input.github_repo()
        })
        # Save settings to bookmark
        session.write_state(github_settings.get())

    @reactive.Effect
    @reactive.event(input.load_settings)
    def _():
        state = session.read_state()
        if state:
            github_settings.set(state)
            ui.update_text("github_username", value=state.get("username", ""))
            ui.update_text("github_token", value=state.get("token", ""))
            ui.update_text("github_repo", value=state.get("repo", ""))

    @reactive.Effect
    @reactive.event(input.add_task)
    def _():
        current_list = tasks[input.selected_list()].get()
        new_task = {
            "name": input.task_name(),
            "description": input.task_description()
        }
        current_list.append(new_task)
        tasks[input.selected_list()].set(current_list)
        ui.update_text("task_name", value="")
        ui.update_text("task_description", value="")

    @reactive.Effect
    @reactive.event(input.delete_task)
    def _():
        if not selected_tasks.get():
            return
        current_list = tasks[input.selected_list()].get()
        current_list = [task for i, task in enumerate(current_list) 
                       if i not in selected_tasks.get()]
        tasks[input.selected_list()].set(current_list)
        selected_tasks.set(set())

    @reactive.Effect
    @reactive.event(input.move_tasks)
    def _():
        if not selected_tasks.get():
            return
        source_list = tasks[input.selected_list()].get()
        target_list = tasks[input.target_list()].get()
        
        moved_tasks = [task for i, task in enumerate(source_list) 
                      if i in selected_tasks.get()]
        remaining_tasks = [task for i, task in enumerate(source_list) 
                         if i not in selected_tasks.get()]
        
        target_list.extend(moved_tasks)
        tasks[input.target_list()].set(target_list)
        tasks[input.selected_list()].set(remaining_tasks)
        selected_tasks.set(set())

    @reactive.Effect
    @reactive.event(input.save_current)
    def _():
        current_list = tasks[input.selected_list()].get()
        save_github_file(f"{input.selected_list()}.json", current_list)

    @reactive.Effect
    @reactive.event(input.load_current)
    def _():
        data = get_github_file(f"{input.selected_list()}.json")
        if data:
            tasks[input.selected_list()].set(data)

    @reactive.Effect
    @reactive.event(input.save_all)
    def _():
        for list_name in TASK_LISTS:
            save_github_file(f"{list_name}.json", tasks[list_name].get())

    @reactive.Effect
    @reactive.event(input.load_all)
    def _():
        for list_name in TASK_LISTS:
            data = get_github_file(f"{list_name}.json")
            if data:
                tasks[list_name].set(data)

    @output
    @render.ui
    def task_list():
        current_tasks = tasks[input.selected_list()].get()
        
        task_elements = []
        for i, task in enumerate(current_tasks):
            is_selected = i in selected_tasks.get()
            task_elements.append(
                ui.div(
                    {"class": "task-item", "style": "padding: 10px; border: 1px solid #ddd; margin: 5px;"},
                    ui.input_checkbox(
                        f"task_{i}",
                        label=task["name"],
                        value=is_selected
                    ),
                    ui.tags.p(task["description"])
                )
            )
        
        return ui.div(task_elements)

    @reactive.Effect
    def _():
        current_tasks = tasks[input.selected_list()].get()
        selected = set()
        
        for i in range(len(current_tasks)):
            checkbox_id = f"task_{i}"
            if hasattr(input, checkbox_id) and input[checkbox_id]():
                selected.add(i)
        
        selected_tasks.set(selected)

app = App(app_ui, server)