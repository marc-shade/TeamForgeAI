# ui_elements.py
import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os
import ollama
from ollama_utils import *
from model_tests import *
import requests
import re
from langchain_community.embeddings import OllamaEmbeddings # Updated import
from langchain_community.vectorstores import Chroma # Updated import
from langchain.text_splitter import CharacterTextSplitter
from langchain.docstore.document import Document
from prompts import get_agent_prompt, get_metacognitive_prompt, manage_prompts

def list_local_models():
    response = requests.get(f"{OLLAMA_URL}/tags")
    response.raise_for_status()
    models = response.json().get("models", [])
    if not models:
        st.write("No local models available.")
        return
    
    # Prepare data for the dataframe
    data = []
    for model in models:
        size_gb = model.get('size', 0) / (1024**3)  # Convert bytes to GB
        modified_at = model.get('modified_at', 'Unknown')
        if modified_at != 'Unknown':
            modified_at = datetime.fromisoformat(modified_at).strftime('%Y-%m-%d %H:%M:%S')
        data.append({
            "Model Name": model['name'],
            "Size (GB)": size_gb,
            "Modified At": modified_at
        })
    
    # Create a pandas dataframe
    df = pd.DataFrame(data)

    # Calculate height based on the number of rows
    row_height = 35  # Set row height
    height = row_height * len(df) + 35  # Calculate height
    
    # Display the dataframe with Streamlit
    st.dataframe(df, use_container_width=True, height=height, hide_index=True)

def update_model_selection(selected_models, key):
    """Callback function to update session state during form submission."""
    st.session_state[key] = selected_models

@st.cache_data  # Cache the comparison and visualization logic
def run_comparison(selected_models, prompt, temperature, max_tokens, presence_penalty, frequency_penalty):
    results = performance_test(selected_models, prompt, temperature, max_tokens, presence_penalty, frequency_penalty)

    # Prepare data for visualization
    models = list(results.keys())  # Get models from results
    times = [results[model][1] for model in models]
    tokens_per_second = [
        results[model][2] / (results[model][3] / (10**9)) if results[model][2] and results[model][3] else 0
        for model in models
    ]

    df = pd.DataFrame({"Model": models, "Time (seconds)": times, "Tokens/second": tokens_per_second})

    return results, df, tokens_per_second, models  # Return models

def model_comparison_test():
    st.header("Model Comparison by Response Quality")

    # Refresh available_models list
    available_models = get_available_models()

    # Initialize selected_models in session state if it doesn't exist
    if "selected_models" not in st.session_state:
        st.session_state.selected_models = []

    # Pass the session state variable as the default for st.multiselect
    selected_models = st.multiselect(
        "Select the models you want to compare:",
        available_models,
        default=st.session_state.selected_models,  # Use session state for default
        key="model_comparison_models"  # Unique key for this multiselect
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.5, step=0.1)
    with col2:
        max_tokens = st.slider("Max Tokens", min_value=100, max_value=32000, value=4000, step=100)
    with col3:
        presence_penalty = st.slider("Presence Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)
    with col4:
        frequency_penalty = st.slider("Frequency Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)

    prompt = st.text_area("Enter the prompt:", value="Write a short story about a brave knight.")

    # Check if the button is clicked
    if st.button(label='Compare Models'):
        if selected_models:
            # Run the comparison and get the results, dataframe, tokens_per_second, and models
            results, df, tokens_per_second, models = run_comparison(selected_models, prompt, temperature, max_tokens, presence_penalty, frequency_penalty)

            # Plot the results using st.bar_chart
            st.bar_chart(df, x="Model", y=["Time (seconds)", "Tokens/second"], color=["#4CAF50", "#FFC107"])  # Green and amber

            for model, (result, elapsed_time, eval_count, eval_duration) in results.items():
                st.subheader(f"Results for {model} (Time taken: {elapsed_time:.2f} seconds, Tokens/second: {tokens_per_second[models.index(model)]:.2f}):")
                st.write(result)
                st.write("JSON Handling Capability: ", "✅" if check_json_handling(model, temperature, max_tokens, presence_penalty, frequency_penalty) else "❌")
                st.write("Function Calling Capability: ", "✅" if check_function_calling(model, temperature, max_tokens, presence_penalty, frequency_penalty) else "❌")
        else:
            st.warning("Please select at least one model.")

def vision_comparison_test():
    st.header("Vision Model Comparison")

    # Refresh available_models list
    available_models = get_available_models()

    # Initialize selected_vision_models in session state if it doesn't exist
    if "selected_vision_models" not in st.session_state:
        st.session_state.selected_vision_models = []

    # Pass the session state variable as the default for st.multiselect
    selected_models = st.multiselect(
        "Select the models you want to compare:",
        available_models,
        default=st.session_state.selected_vision_models,  # Use session state for default
        key="vision_comparison_models"  # Unique key for this multiselect
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.5, step=0.1)
    with col2:
        max_tokens = st.slider("Max Tokens", min_value=100, max_value=32000, value=4000, step=100)
    with col3:
        presence_penalty = st.slider("Presence Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)
    with col4:
        frequency_penalty = st.slider("Frequency Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)

    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "png"])

    # Check if the button is clicked
    if st.button(label='Compare Vision Models'):
        if uploaded_file is not None:
            if selected_models:
                # Display the uploaded image
                st.image(uploaded_file, caption="Uploaded Image", use_column_width=True)

                results = {}
                for model in selected_models:
                    # Reset file pointer to the beginning
                    uploaded_file.seek(0)

                    start_time = time.time()
                    try:
                        # Use ollama.chat for vision tests
                        response = ollama.chat(
                            model=model,
                            messages=[
                                {
                                    'role': 'user',
                                    'content': 'Describe this image:',
                                    'images': [uploaded_file]
                                }
                            ]
                        )
                        result = response['message']['content']
                        print(f"Model: {model}, Result: {result}")  # Debug statement
                    except Exception as e:
                        result = f"An error occurred: {str(e)}"
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    results[model] = (result, elapsed_time)
                    time.sleep(0.1)

                # Display the LLM response text and time taken
                for model, (result, elapsed_time) in results.items():
                    st.subheader(f"Results for {model} (Time taken: {elapsed_time:.2f} seconds):")
                    st.write(result)

                # Prepare data for visualization (after displaying responses)
                models = list(results.keys())
                times = [results[model][1] for model in models]
                df = pd.DataFrame({"Model": models, "Time (seconds)": times})

                # Plot the results
                st.bar_chart(df, x="Model", y="Time (seconds)", color="#4CAF50")
            else:
                st.warning("Please select at least one model.")
        else:
            st.warning("Please upload an image.")

def contextual_response_test():
    st.header("Contextual Response Test by Model")

    # Refresh available_models list
    available_models = get_available_models()

    # Initialize selected_model in session state if it doesn't exist
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = available_models[0] if available_models else None

    # Use a separate key for the selectbox
    selectbox_key = "contextual_test_model_selector"

    # Update selected_model when selectbox changes
    if selectbox_key in st.session_state:
        st.session_state.selected_model = st.session_state[selectbox_key]

    selected_model = st.selectbox(
        "Select the model you want to test:", 
        available_models, 
        key=selectbox_key,
        index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0
    )

    prompts = st.text_area("Enter the prompts (one per line):", value="Hi, how are you?\nWhat's your name?\nTell me a joke.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.5, step=0.1)
    with col2:
        max_tokens = st.slider("Max Tokens", min_value=100, max_value=32000, value=4000, step=100)
    with col3:
        presence_penalty = st.slider("Presence Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)
    with col4:
        frequency_penalty = st.slider("Frequency Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)

    if st.button("Start Contextual Test", key="start_contextual_test"):
        prompt_list = [p.strip() for p in prompts.split("\n")]
        context = []
        times = []
        tokens_per_second_list = []
        for i, prompt in enumerate(prompt_list):
            start_time = time.time()
            result, context, eval_count, eval_duration = call_ollama_endpoint(
                selected_model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                context=context,
            )
            end_time = time.time()
            elapsed_time = end_time - start_time
            times.append(elapsed_time)
            tokens_per_second = eval_count / (eval_duration / (10**9)) if eval_count and eval_duration else 0
            tokens_per_second_list.append(tokens_per_second)
            st.subheader(f"Prompt {i+1}: {prompt} (Time taken: {elapsed_time:.2f} seconds, Tokens/second: {tokens_per_second:.2f}):")
            st.write(f"Response: {result}")

        # Prepare data for visualization
        data = {"Prompt": prompt_list, "Time (seconds)": times, "Tokens/second": tokens_per_second_list}
        df = pd.DataFrame(data)

        # Plot the results using st.bar_chart
        st.bar_chart(df, x="Prompt", y=["Time (seconds)", "Tokens/second"], color=["#4CAF50", "#FFC107"])  # Green and amber

        st.write("JSON Handling Capability: ", "✅" if check_json_handling(selected_model, temperature, max_tokens, presence_penalty, frequency_penalty) else "❌")
        st.write("Function Calling Capability: ", "✅" if check_function_calling(selected_model, temperature, max_tokens, presence_penalty, frequency_penalty) else "❌")

def feature_test():
    st.header("Model Feature Test")
    
    # Refresh available_models list
    available_models = get_available_models()

    # Initialize selected_model in session state if it doesn't exist
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = available_models[0] if available_models else None

    # Use a separate key for the selectbox
    selectbox_key = "feature_test_model_selector"

    # Update selected_model when selectbox changes
    if selectbox_key in st.session_state:
        st.session_state.selected_model = st.session_state[selectbox_key]

    selected_model = st.selectbox(
        "Select the model you want to test:", 
        available_models, 
        key=selectbox_key,
        index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.5, step=0.1)
    with col2:
        max_tokens = st.slider("Max Tokens", min_value=100, max_value=32000, value=4000, step=100)
    with col3:
        presence_penalty = st.slider("Presence Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)
    with col4:
        frequency_penalty = st.slider("Frequency Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)

    if st.button("Run Feature Test", key="run_feature_test"):
        json_result = check_json_handling(selected_model, temperature, max_tokens, presence_penalty, frequency_penalty)
        function_result = check_function_calling(selected_model, temperature, max_tokens, presence_penalty, frequency_penalty)

        st.markdown(f"### JSON Handling Capability: {'✅ Success!' if json_result else '❌ Failure!'}")
        st.markdown(f"### Function Calling Capability: {'✅ Success!' if function_result else '❌ Failure!'}")

        # Prepare data for visualization
        data = {"Feature": ['JSON Handling', 'Function Calling'], "Result": [json_result, function_result]}
        df = pd.DataFrame(data)

        # Plot the results using st.bar_chart
        st.bar_chart(df, x="Feature", y="Result", color="#4CAF50")

def list_models():
    st.header("List Local Models")
    models = list_local_models()
    if models:
        # Prepare data for the dataframe
        data = []
        for model in models:
            size_gb = model.get('size', 0) / (1024**3)  # Convert bytes to GB
            modified_at = model.get('modified_at', 'Unknown')
            if modified_at != 'Unknown':
                modified_at = datetime.fromisoformat(modified_at).strftime('%Y-%m-%d %H:%M:%S')
            data.append({
                "Model Name": model['name'],
                "Size (GB)": size_gb,
                "Modified At": modified_at
            })
        
        # Create a pandas dataframe
        df = pd.DataFrame(data)

        # Calculate height based on the number of rows
        row_height = 35  # Set row height
        height = row_height * len(df) + 35  # Calculate height
        
        # Display the dataframe with Streamlit
        st.dataframe(df, use_container_width=True, height=height, hide_index=True)

def pull_models():
    st.header("Pull a Model from Ollama Library")
    st.write("Enter the exact name of the model you want to pull from the Ollama library. You can just paste the whole model snippet from the model library page like 'ollama run llava-phi3' or you can just enter the model name like 'llava-phi3' and then click 'Pull Model' to begin the download. The progress of the download will be displayed below.")
    model_name = st.text_input("Enter the name of the model you want to pull:")
    if st.button("Pull Model", key="pull_model"):
        if model_name:
            # Strip off "ollama run" or "ollama pull" from the beginning
            model_name = model_name.replace("ollama run ", "").replace("ollama pull ", "").strip()

            result = pull_model(model_name)
            if any("error" in status for status in result):
                st.warning(f"Model '{model_name}' not found. Please make sure you've entered the correct model name. "
                           f"Model names often include a ':' to specify the variant. For example: 'mistral:instruct'")
            else:
                for status in result:
                    st.write(status)
        else:
            st.error("Please enter a model name.")

def show_model_details():
    st.header("Show Model Information")
    
    # Refresh available_models list
    available_models = get_available_models()

    # Initialize selected_model in session state if it doesn't exist
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = available_models[0] if available_models else None

    # Use a separate key for the selectbox
    selectbox_key = "show_model_details_model_selector"

    # Update selected_model when selectbox changes
    if selectbox_key in st.session_state:
        st.session_state.selected_model = st.session_state[selectbox_key]

    selected_model = st.selectbox(
        "Select the model you want to show details for:", 
        available_models, 
        key=selectbox_key,
        index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0
    )

    if st.button("Show Model Information", key="show_model_information"):
        details = show_model_info(selected_model)
        st.json(details)

def remove_model_ui():
    st.header("Remove a Model")
    
    # Refresh available_models list
    available_models = get_available_models()

    # Initialize selected_model in session state if it doesn't exist
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = available_models[0] if available_models else None

    # Use a separate key for the selectbox
    selectbox_key = "remove_model_ui_model_selector"

    # Update selected_model when selectbox changes
    if selectbox_key in st.session_state:
        st.session_state.selected_model = st.session_state[selectbox_key]

    selected_model = st.selectbox(
        "Select the model you want to remove:", 
        available_models, 
        key=selectbox_key,
        index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0
    )

    confirm_label = f"❌ Confirm removal of model `{selected_model}`"
    confirm = st.checkbox(confirm_label)
    if st.button("Remove Model", key="remove_model") and confirm:
        if selected_model:
            result = remove_model(selected_model)
            st.write(result["message"])

            # Clear the cache of get_available_models
            get_available_models.clear()

            # Update the list of available models
            st.session_state.available_models = get_available_models()
            # Update selected_model if it was removed
            if selected_model not in st.session_state.available_models:
                st.session_state.selected_model = st.session_state.available_models[0] if st.session_state.available_models else None
            st.rerun()
        else:
            st.error("Please select a model.")

def update_models():
    st.header("Update Local Models")
    available_models = get_available_models()
    if st.button("Update All Models"):
        for model_name in available_models:
            # Skip custom models (those with a ':' in the name)
            if 'gpt' in model_name:
                st.write(f"Skipping custom model: `{model_name}`")
                continue
            st.write(f"Updating model: `{model_name}`")
            pull_model(model_name)
        st.success("All models updated successfully!")

def chat_interface():
    st.header("Chat with a Model")
    
    # Initialize session state variables
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "workspace_items" not in st.session_state:
        st.session_state.workspace_items = []
    if "agent_type" not in st.session_state:
        st.session_state.agent_type = "None"
    if "metacognitive_type" not in st.session_state:
        st.session_state.metacognitive_type = "None"
    if "selected_model" not in st.session_state:
        available_models = get_available_models()
        st.session_state.selected_model = available_models[0] if available_models else None
    
    # Create tabs for Chat, Workspace, and Files
    chat_tab, workspace_tab, files_tab_ui = st.tabs(["Chat", "Workspace", "Files"])

    with chat_tab:
        # Settings (Collapsible, open by default)
        with st.expander("Settings", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                available_models = get_available_models()
                selected_model = st.selectbox(
                    "📦 Select a Model:", 
                    available_models, 
                    key="selected_model",
                    index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0
                )
            with col2:
                # Add Agent Type selection
                agent_types = ["None"] + list(get_agent_prompt().keys())
                agent_type = st.selectbox("🧑‍💼 Select Agent Type:", agent_types, key="agent_type")
            with col3:
                # Add Metacognitive Type selection
                metacognitive_types = ["None"] + list(get_metacognitive_prompt().keys())
                metacognitive_type = st.selectbox("🧠 Select Metacognitive Type:", metacognitive_types, key="metacognitive_type")
            with col4:
                # Add Corpus selection
                files_folder = "files"
                if not os.path.exists(files_folder):
                    os.makedirs(files_folder)
                corpus_options = ["None"] + [f for f in os.listdir(files_folder) if os.path.isfile(os.path.join(files_folder, f))]
                selected_corpus = st.selectbox("📚 Select Corpus:", corpus_options, key="selected_corpus")

        # Advanced Settings (Collapsible, collapsed by default)
        with st.expander("Advanced Settings", expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                temperature = st.slider("🌡️ Temperature", min_value=0.0, max_value=1.0, value=0.5, step=0.1, key="temperature_slider_chat")
            with col2:
                max_tokens = st.slider("📊 Max Tokens", min_value=100, max_value=32000, value=4000, step=100, key="max_tokens_slider_chat")
            with col3:
                presence_penalty = st.slider("🚫 Presence Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1, key="presence_penalty_slider_chat")
            with col4:
                frequency_penalty = st.slider("🔁 Frequency Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1, key="frequency_penalty_slider_chat")

        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    code_blocks = extract_code_blocks(message["content"])
                    for code_block in code_blocks:
                        st.code(code_block)
                    non_code_parts = re.split(r'```[\s\S]*?```', message["content"])
                    for part in non_code_parts:
                        st.markdown(part.strip())
                else:
                    st.markdown(message["content"])

        # Get user input
        if prompt := st.chat_input("What is up my person?", key="chat_input"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""

                # Combine agent type and metacognitive type prompts
                combined_prompt = ""
                if agent_type != "None":
                    combined_prompt += get_agent_prompt()[agent_type] + "\n\n"
                if metacognitive_type != "None":
                    combined_prompt += get_metacognitive_prompt()[metacognitive_type] + "\n\n"

                # Include chat history and corpus context
                chat_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.chat_history])
                if selected_corpus != "None":
                    corpus_context = get_corpus_context(selected_corpus, prompt)
                    final_prompt = f"{combined_prompt}{chat_history}\n\nContext: {corpus_context}\n\nUser: {prompt}"
                else:
                    final_prompt = f"{combined_prompt}{chat_history}\n\nUser: {prompt}"

                for response_chunk in ollama.generate(st.session_state.selected_model, final_prompt, stream=True):
                    full_response += response_chunk["response"]
                    response_placeholder.markdown(full_response)
                st.session_state.chat_history.append({"role": "assistant", "content": full_response})

            # Automatically detect and save code to workspace
            code_blocks = extract_code_blocks(full_response)
            for code_block in code_blocks:
                st.session_state.workspace_items.append({
                    "type": "code",
                    "content": code_block,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            if code_blocks:
                st.success(f"{len(code_blocks)} code block(s) automatically saved to Workspace")

    # Workspace tab
    with workspace_tab:
        st.subheader("Workspace")
        
        # Display workspace items
        for index, item in enumerate(st.session_state.workspace_items):
            with st.expander(f"Item {index + 1} - {item['timestamp']}"):
                if item['type'] == 'code':
                    st.code(item['content'])
                else:
                    st.write(item['content'])
                if st.button(f"Remove Item {index + 1}"):
                    st.session_state.workspace_items.pop(index)
                    st.rerun()

        # Option to add a new workspace item manually
        new_item = st.text_area("Add a new item to the workspace:")
        if st.button("Add to Workspace"):
            if new_item:
                st.session_state.workspace_items.append({
                    "type": "text",
                    "content": new_item,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                st.success("New item added to Workspace")
                st.rerun()

    # Files tab
    with files_tab_ui:
        files_tab()

def files_tab():
    st.subheader("Files")
    files_folder = "files"
    if not os.path.exists(files_folder):
        os.makedirs(files_folder)
    files = [f for f in os.listdir(files_folder) if os.path.isfile(os.path.join(files_folder, f))]

    for file in files:
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.write(file)
        with col2:
            if file.endswith('.pdf'):
                st.button("📥", key=f"download_{file}")
            else:
                st.button("👁️", key=f"view_{file}")
        with col3:
            if not file.endswith('.pdf'):
                st.button("✏️", key=f"edit_{file}")
        with col4:
            st.button("🗑️", key=f"delete_{file}")

    for file in files:
        file_path = os.path.join(files_folder, file)
        
        if st.session_state.get(f"view_{file}", False):
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    file_content = f.read()
                st.text_area("File Content:", value=file_content, height=200, key=f"view_content_{file}")
            except UnicodeDecodeError:
                st.error(f"Unable to decode file {file}. It may be a binary file.")
        
        if st.session_state.get(f"edit_{file}", False):
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    file_content = f.read()
                new_content = st.text_area("Edit File Content:", value=file_content, height=200, key=f"edit_content_{file}")
                if st.button("Save Changes", key=f"save_{file}"):
                    with open(file_path, "w", encoding='utf-8') as f:
                        f.write(new_content)
                    st.success(f"Changes saved to {file}")
            except UnicodeDecodeError:
                st.error(f"Unable to decode file {file}. It may be a binary file.")
        
        if st.session_state.get(f"download_{file}", False):
            if file.endswith('.pdf'):
                with open(file_path, "rb") as pdf_file:
                    pdf_bytes = pdf_file.read()
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=file,
                    mime='application/pdf',
                )
            else:
                with open(file_path, "r", encoding='utf-8') as f:
                    file_content = f.read()
                st.download_button(
                    label="Download File",
                    data=file_content,
                    file_name=file,
                    mime='text/plain',
                )
        
        if st.session_state.get(f"delete_{file}", False):
            os.remove(file_path)
            st.success(f"File {file} deleted.")
            st.experimental_rerun()
    

   # File upload section
    uploaded_file = st.file_uploader("Upload a file", type=['txt', 'pdf', 'json'])
    if uploaded_file is not None:
        file_path = os.path.join(files_folder, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"File {uploaded_file.name} uploaded successfully!")
        st.experimental_rerun()

    # Save chat and workspace (existing code)
    if st.button("Save Chat and Workspace"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"chat_and_workspace_{timestamp}"
        chat_name = st.text_input("Enter a name for the save:", value=default_filename)
        if chat_name:
            save_data = {
                "chat_history": st.session_state.chat_history,
                "workspace_items": st.session_state.workspace_items
            }
            # Create the 'sessions' folder if it doesn't exist
            sessions_folder = "sessions"
            if not os.path.exists(sessions_folder):
                os.makedirs(sessions_folder)
            file_path = os.path.join(sessions_folder, chat_name + ".json")
            with open(file_path, "w") as f:
                json.dump(save_data, f)
            st.success(f"Chat and Workspace saved to {chat_name}")

    # Load/Rename/Delete chat and workspace (existing code)
    st.sidebar.subheader("Saved Chats and Workspaces")
    sessions_folder = "sessions"
    if not os.path.exists(sessions_folder):
        os.makedirs(sessions_folder)
    saved_files = [f for f in os.listdir(sessions_folder) if f.endswith(".json")]

    if "rename_file" not in st.session_state:
        st.session_state.rename_file = None

    for file in saved_files:
        col1, col2, col3 = st.sidebar.columns([3, 1, 1])
        with col1:
            file_name = os.path.splitext(file)[0]
            if st.button(file_name):
                file_path = os.path.join(sessions_folder, file)
                with open(file_path, "r") as f:
                    loaded_data = json.load(f)
                st.session_state.chat_history = loaded_data.get("chat_history", [])
                st.session_state.workspace_items = loaded_data.get("workspace_items", [])
                st.success(f"Loaded {file_name}")
                st.rerun()
        with col2:
            if st.button("✏️", key=f"rename_{file}"):
                st.session_state.rename_file = file
                st.rerun()
        with col3:
            if st.button("🗑️", key=f"delete_{file}"):
                file_path = os.path.join(sessions_folder, file)
                os.remove(file_path)
                st.success(f"File {file_name} deleted.")
                st.rerun()

    if st.session_state.rename_file:
        current_name = os.path.splitext(st.session_state.rename_file)[0]
        new_name = st.text_input("Rename file:", value=current_name)
        if new_name:
            old_file_path = os.path.join(sessions_folder, st.session_state.rename_file)
            new_file_path = os.path.join(sessions_folder, new_name + ".json")
            if new_file_path != old_file_path:
                os.rename(old_file_path, new_file_path)
                st.success(f"File renamed to {new_name}")
                st.session_state.rename_file = None
                st.cache_resource.clear()
                st.rerun()

def extract_code_blocks(text):
    # Simple regex to extract code blocks (text between triple backticks)
    code_blocks = re.findall(r'```[\s\S]*?```', text)
    # Remove the backticks
    return [block.strip('`').strip() for block in code_blocks]

def get_corpus_context(corpus_file, query):
    # Load and split the corpus file
    files_folder = "files"
    if not os.path.exists(files_folder):
        os.makedirs(files_folder)
    try:
        with open(os.path.join(files_folder, corpus_file), "r", encoding='utf-8') as f:
            corpus_text = f.read()
    except UnicodeDecodeError:
        return "Error: Unable to decode the corpus file. Please ensure it's a text file."

    # Add progress bar for reading the corpus
    st.info(f"Reading corpus file: {corpus_file}")
    progress_bar = st.progress(0)
    total_chars = len(corpus_text)
    chars_processed = 0

    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = []
    for chunk in text_splitter.split_text(corpus_text):
        texts.append(chunk)
        chars_processed += len(chunk)
        progress = chars_processed / total_chars
        progress_bar.progress(progress)

    # Create Langchain documents
    docs = [Document(page_content=t) for t in texts]

    # Create and load the vector database
    st.info("Creating vector database...")
    embeddings = OllamaEmbeddings()
    db = Chroma.from_documents(docs, embeddings, persist_directory="./chroma_db")
    db.persist()

    # Perform similarity search
    st.info("Performing similarity search...")
    results = db.similarity_search(query, k=3)
    st.info("Done!")
    return "\n".join([doc.page_content for doc in results])