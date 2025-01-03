from shiny import App, reactive, render, ui

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
        ui.output_ui("move_controls"),
        ui.output_ui("edit_controls"),
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
        ui.output_ui("task_lists_display")
    )
)

def server(input, output, session):
    # Create a dictionary to store tasks and descriptions for each list
    lists_data = reactive.value({
        list_id: {"tasks": [], "descriptions": []}
        for list_id in LIST_NAMES.keys()
    })
    
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
                        ui.h4(f"{i}. {task}"),
                        ui.p(desc) if desc.strip() else None,
                        style="margin-bottom: 1em;"
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
        editing.set(False)

app = App(app_ui, server)