from shiny import App, reactive, render, ui
import json
import base64
import requests
import os

# Define the list names
LIST_NAMES = {
    "list1": "Personal Tasks",
    "list2": "Work Tasks",
    "list3": "Shopping List",
    "list4": "Project Ideas",
    "list5": "Books to Read",
    "list6": "Movies to Watch",
    "list7": "Goals",
    "list8": "Miscellaneous"
}

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_select(
            "active_list",
            "Working List (for adding/editing)",
            LIST_NAMES
        ),
        ui.hr(),
        ui.input_text("task", "Enter Task"),
        ui.input_text("description", "Enter Description"),
        ui.input_action_button("add", "Add Task", class_="btn-primary"),
        ui.hr(),
        ui.h4("Manage Tasks"),
        ui.output_ui("task_selector"),
        ui.output_ui("edit_controls"),  # Moved up
        ui.hr(),  # Added hr here
        ui.output_ui("move_controls"),  # Moved down
        ui.hr(),

        # Add GitHub save controls
        ui.h4("Save to GitHub"),
        ui.input_text(
            "github_repo",
            "Repository (user/repo)",
            value="",
            autocomplete="username/rep"  # Hint to browser this is a username field
        ),
        ui.input_password(  # Simple password input
            "github_token",
            "Github Token",
            value=""
        ),
        
     #   ui.input_text("github_path", "File path (e.g., tasks.txt)"),
        ui.output_text("github_status_output"),
     #   ui.input_action_button("save_github", "Save to GitHub", class_="btn-success"),        
        ui.input_action_button("load_github", "Load from GitHub", class_="btn-info"),
       
        width=350
    ),

    ui.card(
        ui.row(
            ui.column(12,
                ui.input_selectize(
                    "display_lists",
                    "Select Lists to Display",
                    LIST_NAMES,
                    multiple=True,
                    selected=["list1"]
                )
            )
        ),
        ui.output_ui("unsaved_changes_alert"),  # Add this line
        ui.output_ui("task_lists_display")
    )
)

def server(input, output, session):
    # Create a dictionary to store tasks and descriptions for each list
    lists_data = reactive.value({
        list_id: {"tasks": [], "descriptions": []}
        for list_id in LIST_NAMES.keys()
    })
    
    changes_unsaved = reactive.value(False)
    editing = reactive.value(False)
    

           

    def get_current_list():
        return lists_data.get()[input.active_list()]

    @reactive.effect
    @reactive.event(input.add)
    def add_task():
        if input.task().strip():
            current_data = lists_data.get().copy()
            current_list = current_data[input.active_list()]
            
            current_list["tasks"].append(input.task())
            current_list["descriptions"].append(input.description())
            
            lists_data.set(current_data)
            changes_unsaved.set(True)  # Add this line
            ui.update_text("task", value="")
            ui.update_text("description", value="")

    @output
    @render.ui
    def task_selector():
        current_list = get_current_list()
        if not current_list["tasks"]:
            return ui.p("No tasks in this list")
        
        options = {str(i): f"{i}. {task}" 
                  for i, task in enumerate(current_list["tasks"], 1)}
        
        return ui.div(
            ui.input_checkbox_group(
                "selected_tasks",
                "Select Tasks to Move/Edit",
                options
            )
        )

    @output
    @render.ui
    def task_lists_display():
        selected_lists = input.display_lists()
        if not selected_lists:
            return ui.p("Please select lists to display")
        
        col_width = 12 // len(selected_lists)
        col_width = max(3, min(12, col_width))
        
        columns = []
        for list_id in selected_lists:
            current_list = lists_data.get()[list_id]
            current_tasks = current_list["tasks"]
            current_descriptions = current_list["descriptions"]
            
            task_items = []
            task_items.append(ui.h3(LIST_NAMES[list_id]))
            
            if not current_tasks:
                task_items.append(ui.p("No tasks in this list"))
            else:
                for i, (task, desc) in enumerate(zip(current_tasks, current_descriptions), 1):
                    task_html = ui.div(
                        ui.h5(f"• {task}"),
                        ui.p(desc,style="text-indent:50px"),
                        style="margin-bottom: 0;"
                    )
                    task_items.append(task_html)
                
            column = ui.column(
                col_width,
                ui.card(
                    *task_items,
                    style="height: 100%;"
                )
            )
            columns.append(column)
        
        return ui.row(*columns)

    @output
    @render.ui
    def move_controls():
        if not input.selected_tasks():
            return ui.div()
            
        current_list_id = input.active_list()
        move_options = {k: v for k, v in LIST_NAMES.items() if k != current_list_id}
        
        return ui.div(
            ui.hr(),
            ui.h4("Move Tasks"),
            ui.input_select(
                "move_to_list",
                "Select Destination List",
                move_options
            ),
            ui.input_action_button("move_tasks", "Move Selected Tasks", class_="btn-info"),
        )

    @output
    @render.ui
    def edit_controls():
        if not input.selected_tasks() or len(input.selected_tasks()) != 1:
            return ui.div()
        
        if editing.get():
            task_idx = int(input.selected_tasks()[0]) - 1
            current_list = get_current_list()
            
            return ui.div(
                ui.hr(),
                ui.h4("Edit Task"),
                ui.input_text(
                    "edit_task",
                    "Task",
                    value=current_list["tasks"][task_idx]
                ),
                ui.input_text(
                    "edit_description",
                    "Description",
                    value=current_list["descriptions"][task_idx]
                ),
                ui.input_action_button("save_edit", "Save", class_="btn-success"),
                ui.input_action_button("cancel_edit", "Cancel", class_="btn-secondary"),
            )
        else:
            return ui.div(
                        ui.hr(),
                        ui.input_action_button("start_edit", "Edit Selected Task", class_="btn-warning"),
                        ui.br(),
                        ui.br(),
                        ui.div(
                            ui.input_action_button("move_up", "↑ Move Up", class_="btn-primary"),
                            ui.input_action_button("move_down", "↓ Move Down", class_="btn-primary"),
                            style="display: flex; gap: 10px;"
                        )
                    )

    @reactive.effect
    @reactive.event(input.move_tasks)
    def move_selected_tasks():
        if not input.selected_tasks():
            return
            
        selected_indices = [int(idx) - 1 for idx in input.selected_tasks()]
        source_list_id = input.active_list()
        target_list_id = input.move_to_list()
        
        current_data = lists_data.get().copy()
        source_list = current_data[source_list_id]
        target_list = current_data[target_list_id]
        
        # Get tasks and descriptions to move
        tasks_to_move = [source_list["tasks"][i] for i in selected_indices]
        descriptions_to_move = [source_list["descriptions"][i] for i in selected_indices]
        
        # Add to target list
        target_list["tasks"].extend(tasks_to_move)
        target_list["descriptions"].extend(descriptions_to_move)
        
        # Remove from source list (in reverse order to maintain indices)
        for i in sorted(selected_indices, reverse=True):
            source_list["tasks"].pop(i)
            source_list["descriptions"].pop(i)
        
        lists_data.set(current_data)
        changes_unsaved.set(True)  # Add this line

    @reactive.effect
    @reactive.event(input.start_edit)
    def start_editing():
        editing.set(True)

    @reactive.effect
    @reactive.event(input.cancel_edit)
    def cancel_editing():
        editing.set(False)

    @reactive.effect
    @reactive.event(input.save_edit)
    def save_edit():
        if not input.selected_tasks():
            return
            
        task_idx = int(input.selected_tasks()[0]) - 1
        current_data = lists_data.get().copy()
        current_list = current_data[input.active_list()]
        
        current_list["tasks"][task_idx] = input.edit_task()
        current_list["descriptions"][task_idx] = input.edit_description()
        
        lists_data.set(current_data)
        changes_unsaved.set(True)  # Add this line
        editing.set(False)

    # Add a reactive value for GitHub save status
    github_status = reactive.value("")

    @output
    @render.text
    def github_status_output():
        return github_status.get()

    @reactive.effect
    @reactive.event(input.move_up)
    def move_task_up():
        if not input.selected_tasks() or len(input.selected_tasks()) != 1:
            return
            
        task_idx = int(input.selected_tasks()[0]) - 1
        if task_idx <= 0:  # Can't move up if already at top
            return
            
        current_data = lists_data.get().copy()
        current_list = current_data[input.active_list()]
        
        # Swap tasks
        current_list["tasks"][task_idx], current_list["tasks"][task_idx-1] = \
            current_list["tasks"][task_idx-1], current_list["tasks"][task_idx]
        
        # Swap descriptions
        current_list["descriptions"][task_idx], current_list["descriptions"][task_idx-1] = \
            current_list["descriptions"][task_idx-1], current_list["descriptions"][task_idx]
        
        lists_data.set(current_data)
        changes_unsaved.set(True)  # Add this line
        
        # Update the selection to follow the moved task
        ui.update_checkbox_group(
            "selected_tasks",
            selected=[str(task_idx)]  # Index is 0-based, but UI is 1-based
        )

    @reactive.effect
    @reactive.event(input.move_down)
    def move_task_down():
        if not input.selected_tasks() or len(input.selected_tasks()) != 1:
            return
            
        task_idx = int(input.selected_tasks()[0]) - 1
        current_data = lists_data.get().copy()
        current_list = current_data[input.active_list()]
        
        if task_idx >= len(current_list["tasks"]) - 1:  # Can't move down if already at bottom
            return
            
        # Swap tasks
        current_list["tasks"][task_idx], current_list["tasks"][task_idx+1] = \
            current_list["tasks"][task_idx+1], current_list["tasks"][task_idx]
        
        # Swap descriptions
        current_list["descriptions"][task_idx], current_list["descriptions"][task_idx+1] = \
            current_list["descriptions"][task_idx+1], current_list["descriptions"][task_idx]
        
        lists_data.set(current_data)
        changes_unsaved.set(True)  # Add this line
        
        # Update the selection to follow the moved task
        ui.update_checkbox_group(
            "selected_tasks",
            selected=[str(task_idx + 2)]  # Index is 0-based, but UI is 1-based
        )    
    
    
    
    
    
    @output
    @render.ui
    def unsaved_changes_alert():
        if changes_unsaved.get():
            
            return ui.div(
                ui.card(
                    ui.tags.b("⚠️unsaved changes"),
                    ui.input_action_button(
                        "quick_save", 
                        "Save Changes to GitHub", 
                        class_="btn-success"
                    )
                   # style="background-color: #fff3cd; color: #856404; border-color: #ffeeba; margin-bottom: 0;"
                )
            )
        return ui.div()
    



    @reactive.effect
    @reactive.event(input.quick_save)
    def handle_quick_save():
        if not input.github_token() or not input.github_repo():
            github_status.set("Please fill in GitHub credentials in the sidebar first")
            return

        path = "ToDoList.txt"
        try:
            # Prepare the data
            data = lists_data.get()
            formatted_data = ""
            for list_id, list_name in LIST_NAMES.items():
                formatted_data += f"=== {list_name} ===\n"
                list_content = data[list_id]
                for task, desc in zip(list_content["tasks"], list_content["descriptions"]):
                    formatted_data += f"- {task}\n"
                    if desc.strip():
                        formatted_data += f"  Description: {desc}\n"
                formatted_data += "\n"

            # GitHub API endpoint
            repo = input.github_repo()
            url = f"https://api.github.com/repos/{repo}/contents/{path}"

            # Headers for authentication
            headers = {
                "Authorization": f"token {input.github_token()}",
                "Accept": "application/vnd.github.v3+json"
            }

            # Check if file exists
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    # File exists, get the SHA
                    sha = response.json()["sha"]
                else:
                    sha = None
            except:
                sha = None

            # Prepare the content
            content = base64.b64encode(formatted_data.encode()).decode()

            # Prepare the data for the API request
            data = {
                "message": "Update task lists",
                "content": content,
            }
            if sha:
                data["sha"] = sha

            # Make the API request
            response = requests.put(url, headers=headers, json=data)

            if response.status_code in [200, 201]:
                github_status.set("Successfully saved to GitHub!")
                changes_unsaved.set(False)
            else:
                github_status.set(f"Error saving to GitHub: {response.status_code}")

        except Exception as e:
            github_status.set(f"Error: {str(e)}")
    
    
    
    
    
    
    
    @reactive.effect
    @reactive.event(input.save_github)
    def save_to_github():
        path= "ToDoList.txt"
        if not input.github_token() or not input.github_repo():
            github_status.set("Please fill in all GitHub fields")
            return

        try:
            # Prepare the data
            data = lists_data.get()
            formatted_data = ""
            for list_id, list_name in LIST_NAMES.items():
                formatted_data += f"=== {list_name} ===\n"
                list_content = data[list_id]
                for task, desc in zip(list_content["tasks"], list_content["descriptions"]):
                    formatted_data += f"- {task}\n"
                    if desc.strip():
                        formatted_data += f"  Description: {desc}\n"
                formatted_data += "\n"

            # GitHub API endpoint
            repo = input.github_repo()
            
            url = f"https://api.github.com/repos/{repo}/contents/{path}"

            # Headers for authentication
            headers = {
                "Authorization": f"token {input.github_token()}",
                "Accept": "application/vnd.github.v3+json"
            }

            # Check if file exists
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    # File exists, get the SHA
                    sha = response.json()["sha"]
                else:
                    sha = None
            except:
                sha = None

            # Prepare the content
            content = base64.b64encode(formatted_data.encode()).decode()

            # Prepare the data for the API request
            data = {
                "message": "Update task lists",
                "content": content,
            }
            if sha:
                data["sha"] = sha

            # Make the API request
            response = requests.put(url, headers=headers, json=data)

            if response.status_code in [200, 201]:
                github_status.set("Successfully saved to GitHub!")
            else:
                github_status.set(f"Error saving to GitHub: {response.status_code}")

        except Exception as e:
            github_status.set(f"Error: {str(e)}")



    @reactive.effect
    @reactive.event(input.load_github)      
    def load_from_github():
        path = "ToDoList.txt"
        if not input.github_token() or not input.github_repo():
            github_status.set("Please fill in all GitHub fields")
            return

        try:
            # GitHub API endpoint
            repo = input.github_repo()
            url = f"https://api.github.com/repos/{repo}/contents/{path}"

            # Headers for authentication
            headers = {
                "Authorization": f"token {input.github_token()}",
                "Accept": "application/vnd.github.v3+json"
            }

            # Get the file content
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                # Decode content from base64
                content = base64.b64decode(response.json()["content"]).decode()
                
                # Parse the content
                current_list_id = None
                new_data = {list_id: {"tasks": [], "descriptions": []} 
                        for list_id in LIST_NAMES.keys()}
                
                lines = [line.rstrip() for line in content.split('\n')]
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if not line:
                        i += 1
                        continue
                        
                    # Check if this is a list header
                    if line.startswith('===') and line.endswith('==='):
                        list_name = line.strip('= ')
                        # Find the list_id for this list_name
                        current_list_id = next(
                            (k for k, v in LIST_NAMES.items() if v == list_name),
                            None
                        )
                    # Check if this is a task
                    elif line.startswith('- ') and current_list_id:
                        task = line[2:]  # Remove the '- ' prefix
                        new_data[current_list_id]["tasks"].append(task)
                        
                        # Look ahead for description
                        desc = ""
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if next_line.startswith('  Description:'):
                                desc = next_line[14:].strip()  # Remove '  Description: ' prefix
                                i += 1  # Skip the description line
                        new_data[current_list_id]["descriptions"].append(desc)
                    
                    i += 1

                # Update the lists_data
                lists_data.set(new_data)
                github_status.set("Successfully loaded from GitHub!")
            else:
                github_status.set(f"Error loading from GitHub: {response.status_code}")

        except Exception as e:
            github_status.set(f"Error loading: {str(e)}")

app = App(app_ui, server)
