# TeamForgeAI/skills/project_management.py
import streamlit as st
import re

def project_management(query: str = ""):
    """
    A skill for managing project objectives.

    This skill can be used to:
    - Generate a list of objectives based on a given project description.
    - Add new objectives to the project.
    - Mark objectives as complete or incomplete.

    :param query: A string containing a project description or a command for managing objectives.
    :return: A string containing the current list of objectives or a message indicating the result of the command.
    """
    # Access the current project from session state
    current_project = st.session_state.get("current_project", None)

    if current_project is None:
        return "Error: No active project found."

    # If no query is provided, return the current list of objectives and deliverables
    if not query:
        objectives_str = "Objectives:\n"
        for i, obj in enumerate(current_project.objectives):
            objectives_str += f"{i+1}. [{'x' if obj['done'] else ' '}] {obj['text']}\n"

        deliverables_str = "Deliverables:\n"
        for i, deliverable in enumerate(current_project.deliverables):
            deliverables_str += f"{i+1}. [{'x' if deliverable['done'] else ' '}] {deliverable['text']}\n"

        return objectives_str + "\n" + deliverables_str # Return both objectives and deliverables

    # Handle commands for managing objectives
    commands = {
        "add": lambda obj: current_project.add_objective(obj),
        "done": lambda index: current_project.mark_objective_done(int(index) - 1),
        "undone": lambda index: current_project.mark_objective_undone(int(index) - 1),
    }

    # Parse the query to extract the command and argument
    match = re.match(r"(\w+)\s*(.*)", query)
    if match:
        command, arg = match.groups()
        if command in commands:
            try:
                commands[command](arg)
                return f"Objective {command} successfully."
            except Exception as e:
                return f"Error: {e}"
        else:
            return f"Error: Invalid command '{command}'."
    else:
        return "Error: Invalid query format."