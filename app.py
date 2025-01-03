from shiny import App, reactive, render, ui, session
import pandas as pd
import base64
import urllib3
import json

# List names for the 8 different task lists
TASK_LISTS = [
    "Personal Tasks",
    "Work Tasks",
    "Shopping List",
    "Project Ideas",
    "Learning Goals",
    "Home Maintenance",
    "Health Goals",
    "Miscellaneous"
]

app_ui = ui.page_fluid(
    ui.navset_tab(
        ui.nav_panel("GitHub Settings",
            ui.card(
                ui.input_text("github_token", "GitHub Personal Access Token", placeholder="Enter your GitHub token"),
                ui.input_text("github_repo", "Repository Name", placeholder="username/repository"),
                ui.input_text("github_file", "File Path", value="tasks.txt"),
                ui.p("Note: Make sure you have the correct repository permissions."),
                ui.input_action_button("save_settings", "Save Settings"),
                ui.input_action_button("clear_settings", "Clear Saved Settings")
            )
        ),
        ui.nav_panel("Task Management",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.input_select("current_list", "Select Task List", TASK_LISTS),
                    ui.input_text("task", "Task", placeholder="Enter task"),
                    ui.input_text("description", "Description", placeholder="Enter description"),
                    ui.input_action_button("add", "Add Task"),
                    ui.hr(),
                    ui.p("GitHub Operations:"),
                    ui.input_radio_buttons(
                        "save_mode",
                        "Save Mode",
                        choices=["Current List Only", "All Lists"]
                    ),
                    ui.input_action_button("save", "Save to GitHub"),
                    ui.input_action_button("load", "Load from GitHub"),
                ),
                ui.card(
                    ui.h3(ui.output_text("selected_list_name")),
                    ui.output_table("task_table")
                )
            )
        )
    )
)

def server(input, output, session):
    # Initialize tasks DataFrames for all lists
    tasks_dict = {list_name: reactive.value(pd.DataFrame(columns=['Task', 'Description'])) 
                 for list_name in TASK_LISTS}
    
    @output
    @render.text
    def selected_list_name():
        return f"Current List: {input.current_list()}"

    @reactive.effect
    @reactive.event(input.add)
    def _():
        if not input.task() or not input.description():
            ui.notification_show("Please enter both task and description", type="error")
            return
            
        current_list = input.current_list()
        current_tasks = tasks_dict[current_list].get().copy()
        new_task = pd.DataFrame({
            'Task': [input.task()],
            'Description': [input.description()]
        })
        tasks_dict[current_list].set(pd.concat([current_tasks, new_task], ignore_index=True))
        
        # Clear inputs
        ui.update_text("task", value="")
        ui.update_text("description", value="")
        ui.notification_show("Task added successfully!", type="message")

    @output
    @render.table
    def task_table():
        return tasks_dict[input.current_list()].get()

    @reactive.effect
    @reactive.event(input.save)
    def _():
        if not all([input.github_token(), input.github_repo(), input.github_file()]):
            ui.notification_show("Please fill in all GitHub settings", type="error")
            return

        try:
            # Prepare the content based on save mode
            if input.save_mode() == "Current List Only":
                save_data = {
                    input.current_list(): tasks_dict[input.current_list()].get().to_dict('records')
                }
            else:
                save_data = {
                    list_name: tasks_dict[list_name].get().to_dict('records')
                    for list_name in TASK_LISTS
                }

            # Convert to JSON string
            content = json.dumps(save_data, indent=2)
            content_bytes = content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')

            # GitHub API endpoint
            url = f"https://api.github.com/repos/{input.github_repo()}/contents/{input.github_file()}"
            
            headers = {
                "Authorization": f"token {input.github_token()}",
                "Accept": "application/vnd.github.v3+json"
            }

            http = urllib3.PoolManager()

            # First try to get the file (to get the SHA if it exists)
            try:
                response = http.request('GET', url, headers=headers)
                if response.status == 200:
                    current_file = json.loads(response.data.decode('utf-8'))
                    sha = current_file['sha']
                    data = {
                        "message": "Update tasks",
                        "content": content_base64,
                        "sha": sha
                    }
                else:
                    data = {
                        "message": "Create tasks file",
                        "content": content_base64
                    }
            except:
                data = {
                    "message": "Create tasks file",
                    "content": content_base64
                }

            # Make the PUT request
            response = http.request(
                'PUT',
                url,
                body=json.dumps(data).encode('utf-8'),
                headers=headers
            )

            if response.status in [200, 201]:
                ui.notification_show("Successfully saved to GitHub!", type="message")
            else:
                ui.notification_show("Error saving to GitHub", type="error")

        except Exception as e:
            ui.notification_show(f"Error: {str(e)}", type="error")

    @reactive.effect
    @reactive.event(input.load)
    def _():
        if not all([input.github_token(), input.github_repo(), input.github_file()]):
            ui.notification_show("Please fill in all GitHub settings", type="error")
            return

        try:
            # GitHub API endpoint
            url = f"https://api.github.com/repos/{input.github_repo()}/contents/{input.github_file()}"
            
            headers = {
                "Authorization": f"token {input.github_token()}",
                "Accept": "application/vnd.github.v3+json"
            }

            http = urllib3.PoolManager()
            response = http.request('GET', url, headers=headers)

            if response.status == 200:
                content = json.loads(response.data.decode('utf-8'))
                file_content = base64.b64decode(content['content']).decode('utf-8')
                
                # Load JSON data
                loaded_data = json.loads(file_content)

                if input.save_mode() == "Current List Only":
                    # Only update current list if it exists in loaded data
                    current_list = input.current_list()
                    if current_list in loaded_data:
                        df = pd.DataFrame(loaded_data[current_list])
                        tasks_dict[current_list].set(df)
                else:
                    # Update all lists that exist in loaded data
                    for list_name in TASK_LISTS:
                        if list_name in loaded_data:
                            df = pd.DataFrame(loaded_data[list_name])
                            tasks_dict[list_name].set(df)
                
                ui.notification_show("Successfully loaded from GitHub!", type="message")
            else:
                ui.notification_show("Error loading from GitHub", type="error")

        except Exception as e:
            ui.notification_show(f"Error: {str(e)}", type="error")

app = App(app_ui, server)