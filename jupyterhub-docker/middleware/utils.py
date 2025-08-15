import json
from datetime import datetime
from collections import OrderedDict, Counter

def load_log_file(log_file_path):
    try:
        with open(log_file_path, 'r', encoding='utf-8') as file:
            log_data = json.load(file)
            return log_data
    except:
        with open(log_file_path, 'r', encoding='utf-8') as file:
            data = file.read()
            data = '[' + data[:-1] + ']'
            log_data = json.loads(data)
            return log_data


def get_executed_cell_contents(cell_index, notebook_state):
    if not notebook_state:
        return "", ""
    
    cells = notebook_state.get('notebookContent', {}).get('cells', [])
    if cell_index < len(cells):
        cell = cells[cell_index]
        cell_content = cell.get('source', '')
        cell_outputs = cell.get('outputs', [])
        stdout = ''
        stderr = ''
        result_output = ''

        for output in cell_outputs:
            if output.get('output_type') == 'stream' and output.get('name') == 'stdout':
                stdout += output.get('text', '')
            elif output.get('output_type') == 'error':
                stderr += f"{output.get('ename', '')}: {output.get('evalue', '')}\n"
                stderr += ''.join(output.get('traceback', []))
            elif output.get('output_type') in ['execute_result', 'display_data']:
                if 'text/plain' in output.get('data', {}):
                    result_output += output['data']['text/plain']

        return cell_content, stdout or result_output or stderr
    
    return "", ""


def reconstruct_cell_contents(log_data):
    cell_contents = {}
    cell_edit_times = {}
    events = []
    paste_events = {}

    # Create an ordered list of dictionaries to store the content of each event
    event_dict = []


    for log in log_data:
        event_detail = log.get('eventDetail', {})
        event_name = event_detail.get('eventName', '')
        event_time = event_detail.get('eventTime', '')
        event_info = event_detail.get('eventInfo', {})
        notebook_state = log.get('notebookState', {})
        notebook_path = notebook_state.get('notebookPath', '')

        if event_time:
            event_time_str = datetime.fromtimestamp(event_time / 1000).strftime('%Y-%m-%d %H:%M:%S')

        if event_name == 'NotebookOpenEvent':
            continue
            events.append(f"Opened notebook '{notebook_path}' at {event_time_str}")
            event_dict.append(OrderedDict({'event': 'Opened notebook', 'notebook': notebook_path, 'time': event_time_str}))
        
        elif event_name == 'NotebookHiddenEvent':
            continue
            events.append(f"Closed notebook '{notebook_path}' at {event_time_str}")
            event_dict.append(OrderedDict({'event': 'Closed notebook', 'notebook': notebook_path, 'time': event_time_str}))

        elif event_name == 'NotebookVisibleEvent':
            continue
            events.append(f"Notebook '{notebook_path}' became visible at {event_time_str}")
            event_dict.append(OrderedDict({'event': 'Notebook became visible', 'notebook': notebook_path, 'time': event_time_str}))

        elif event_name == 'CellEditEvent':
            cell_index = event_info.get('index', '')
            changes = event_info.get('changes', [])
            
            if cell_index not in cell_contents:
                cell_contents[cell_index] = []
                cell_edit_times[cell_index] = event_time_str

            if changes:
                if isinstance(changes[0], list):
                    for change in changes:
                        if type(change) == int:
                            continue
                        elif len(change) > 2:
                            pos = change[0]
                            lines = '\n'.join(change[1:])
                            if pos >= len(cell_contents[cell_index]):
                                cell_contents[cell_index].extend([''] * (pos - len(cell_contents[cell_index]) + 1))
                            cell_contents[cell_index][pos:pos+1] = [lines]
                        elif len(change) == 2:
                            pos, char = change
                            if pos >= len(cell_contents[cell_index]):
                                cell_contents[cell_index].extend([''] * (pos - len(cell_contents[cell_index]) + 1))
                            cell_contents[cell_index][pos] = char
                else:
                    if len(changes) >= 2:
                        string_index = changes[0]
                        char_change = changes[1]
                        if isinstance(char_change, list) and len(char_change) == 2:
                            pos, char = char_change
                            if string_index >= len(cell_contents[cell_index]):
                                cell_contents[cell_index].extend([''] * (string_index - len(cell_contents[cell_index]) + 1))
                            cell_contents[cell_index][string_index] = char

            if cell_index in paste_events:
                if paste_events[cell_index] == ''.join(cell_contents[cell_index]):
                    del paste_events[cell_index]
                    continue  # Skip logging this event as it is a duplicate
            
        elif event_name == 'CellExecuteEvent':
            # Log edits for all cells before execution
            for cell_index, content in cell_contents.items():
                content_str = ''.join(content).strip()
                if content_str:
                    start_time = cell_edit_times[cell_index]
                    events.append(f"Edited cell {cell_index} in notebook '{notebook_path}' from {start_time} to {event_time_str}: Added '{content_str}'")
                    event_dict.append(OrderedDict({
                        'event': 'Edited cell', 
                        'notebook': notebook_path, 
                        'time': event_time_str, 
                        'cell_index': cell_index, 
                        'content': content_str
                    }))
                    # Clear cell content after logging
                    cell_contents[cell_index] = []

            cell_indices = [cell.get('index', '') for cell in event_info.get('cells', [])]
            success = event_info.get('success', '')
            if success:
                cell_content, cell_output = get_executed_cell_contents(cell_indices[0], notebook_state)
                events.append(f"Executed cells {cell_indices} in notebook '{notebook_path}' successfully at {event_time_str} with input: {cell_content}")
                event_dict.append(OrderedDict({
                    'event': 'Executed cells', 
                    'notebook': notebook_path, 
                    'time': event_time_str, 
                    'cell_index': cell_indices[0], 
                    'input': cell_content, 
                    'output': cell_output
                }))
            else:
                kernel_error = event_info.get('kernelError', {})
                error_name = kernel_error.get('errorName', 'UnknownError')
                error_value = kernel_error.get('errorValue', 'Unknown error value')

                # Get the content of the cell that caused the error
                cell_content, _ = get_executed_cell_contents(cell_indices[0], notebook_state)
                
                events.append(f"Executed cells {cell_indices} in notebook '{notebook_path}' at {event_time_str} with error: {error_name} - {error_value}. Cell content: '{cell_content}'")
                event_dict.append(OrderedDict({
                    'event': 'Executed cells with error', 
                    'notebook': notebook_path, 
                    'time': event_time_str, 
                    'cell_index': cell_indices[0], 
                    'error': f"{error_name} - {error_value}",
                    'content': cell_content
                }))

        
        elif event_name == 'ClipboardPasteEvent':
            cell_index = event_info.get('cells', [])[0].get('index', '')
            selection = event_info.get('selection', '')

            if cell_index not in cell_contents:
                cell_contents[cell_index] = []
                cell_edit_times[cell_index] = event_time_str

            # If the cell content is empty or shorter than the paste position, extend it
            if len(cell_contents[cell_index]) < 1:
                cell_contents[cell_index].extend([''] * (1 - len(cell_contents[cell_index])))

            # Add the pasted content
            cell_contents[cell_index][0] = selection

            # Log the paste event for potential redundancy checks
            paste_events[cell_index] = selection

            events.append(f"Pasted content into cell {cell_index} in notebook '{notebook_path}' at {event_time_str}: Added '{selection}'")
            event_dict.append(OrderedDict({'event': 'Pasted content', 'notebook': notebook_path, 'time': event_time_str, 'cell_index': cell_index, 'content': selection}))

        elif event_name == 'CellAddEvent':
            cell_index = event_info.get('index', '')
            cell_content = event_info.get('content', '')

            if cell_index not in cell_contents:
                cell_contents[cell_index] = []
                cell_edit_times[cell_index] = event_time_str

            # Add the new cell content
            cell_contents[cell_index].append(cell_content)

            events.append(f"Added new cell {cell_index} in notebook '{notebook_path}' at {event_time_str}: Added '{cell_content}'")
            event_dict.append(OrderedDict({'event': 'Added new cell', 'notebook': notebook_path, 'time': event_time_str, 'cell_index': cell_index, 'content': cell_content}))


    return events, event_dict


def analyze_logs(log_file_path, chat_log_path, start_time, end_time, filter_automated=True):
    log_data = load_log_file(log_file_path)
    log_summary, log_objects = reconstruct_cell_contents(log_data)
    logs = []
    # Load the chat logs
    with open(chat_log_path, 'r') as file:
        chat_data = json.load(file)

    # Convert timestamps
    start_timestamp = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
    end_timestamp = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

    # Filter notebook events
    for event in log_objects:
        event_time = datetime.strptime(event['time'], '%Y-%m-%d %H:%M:%S').timestamp()
        if start_timestamp <= event_time <= end_timestamp:
            logs.append(event)


    for message in chat_data['messages']:
        message_time = message['time']
        if start_timestamp <= message_time <= end_timestamp:
            if filter_automated and 'automated' in message:
                continue
            # Convert timestamp to string
            message['time'] = datetime.fromtimestamp(message_time).strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Remove the message from the list if it is outside the time range
            chat_data['messages'].remove(message)

    return logs, chat_data
