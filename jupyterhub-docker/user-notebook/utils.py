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
    if cell_index is not None and cell_index < len(cells):
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
    events = []
    event_dict = []
    processed_indices = set()
    cell_contents_buffer = {}
    last_assistant_content = {}  # Track last assistant content per cell

    # Pass 1: Identify assistant-inserted content patterns
    for i, log in enumerate(log_data):
        if i in processed_indices:
            continue

        event_detail = log.get('eventDetail', {})
        event_name = event_detail.get('eventName', '')
        
        # Pattern: Assistant inserted code (either into new cell or replacing existing content)
        if event_name == 'CellAddEvent':
            added_cell_index = event_detail.get('eventInfo', {}).get('cells', [{}])[0].get('index')
            # Look for immediate CellEditEvent with bulk content
            for j in range(i + 1, min(i + 6, len(log_data))):
                if j in processed_indices: 
                    continue
                
                future_log = log_data[j]
                future_detail = future_log.get('eventDetail', {})
                if (future_detail.get('eventName') == 'CellEditEvent' and
                    future_detail.get('eventInfo', {}).get('index') == added_cell_index):
                    
                    changes = future_detail.get('eventInfo', {}).get('changes', [])
                    if changes and isinstance(changes[0], list) and len(changes[0]) > 1:
                        content_str = '\n'.join(changes[0][1:])
                        # Heuristic: assistant inserts are typically multi-character or multi-line
                        if len(content_str) > 1 or '\n' in content_str:
                            add_time_str = datetime.fromtimestamp(event_detail.get('eventTime') / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            edit_time_str = datetime.fromtimestamp(future_detail.get('eventTime') / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Add "Added new cell" event
                            event_dict.append(OrderedDict({
                                'event': 'Added new cell',
                                'notebook': log.get('notebookState', {}).get('notebookPath', ''),
                                'time': add_time_str,
                                'cell_index': added_cell_index,
                                'content': ''
                            }))
                            
                            # Add "Inserted code from assistant" event
                            event_dict.append(OrderedDict({
                                'event': 'Inserted code from assistant',
                                'notebook': future_log.get('notebookState', {}).get('notebookPath', ''),
                                'time': edit_time_str,
                                'cell_index': added_cell_index,
                                'content': content_str
                            }))
                            
                            # Mark these events as processed
                            processed_indices.add(i)
                            processed_indices.add(j)
                            
                            # Update buffer and track assistant content
                            cell_contents_buffer[added_cell_index] = content_str
                            last_assistant_content[added_cell_index] = content_str
                            break
        
        # Pattern: Replacement in existing cell (assistant replacing content)
        elif event_name == 'CellEditEvent':
            event_info = event_detail.get('eventInfo', {})
            changes = event_info.get('changes', [])
            cell_index = event_info.get('index')
            
            # Check for replacement pattern (deletion followed by insertion)
            if len(changes) > 1 and isinstance(changes[0], list) and isinstance(changes[1], list):
                content_str = '\n'.join(changes[1][1:])
                edit_time_str = datetime.fromtimestamp(event_detail.get('eventTime') / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                event_dict.append(OrderedDict({
                    'event': 'Inserted code from assistant',
                    'notebook': log.get('notebookState', {}).get('notebookPath', ''),
                    'time': edit_time_str,
                    'cell_index': cell_index,
                    'content': content_str
                }))
                
                processed_indices.add(i)
                cell_contents_buffer[cell_index] = content_str
                last_assistant_content[cell_index] = content_str

    # Pass 2: Process all other events (manual edits, executions, etc.)
    for i, log in enumerate(log_data):
        if i in processed_indices:
            continue
            
        event_detail = log.get('eventDetail', {})
        event_name = event_detail.get('eventName', '')
        event_time = event_detail.get('eventTime')
        event_info = event_detail.get('eventInfo', {})
        notebook_path = log.get('notebookState', {}).get('notebookPath', '')
        event_time_str = datetime.fromtimestamp(event_time / 1000).strftime('%Y-%m-%d %H:%M:%S')

        # Skip navigation events
        if event_name in ['NotebookScrollEvent', 'ActiveCellChangeEvent', 'NotebookHiddenEvent', 'NotebookVisibleEvent', 'NotebookOpenEvent']:
            continue

        # Manual cell addition (without assistant content)
        if event_name == 'CellAddEvent':
            added_cell_index = event_info.get('cells', [{}])[0].get('index')
            event_dict.append(OrderedDict({
                'event': 'Added new cell',
                'notebook': notebook_path,
                'time': event_time_str,
                'cell_index': added_cell_index,
                'content': ''
            }))
            cell_contents_buffer[added_cell_index] = ""
            continue
            
        # Manual cell edits
        elif event_name == 'CellEditEvent':
            cell_index = event_info.get('index')
            changes = event_info.get('changes', [])
            
            # Track manual typing in buffer
            if cell_index not in cell_contents_buffer:
                cell_contents_buffer[cell_index] = ""
            
            # Simple reconstruction of manual edits
            if changes and isinstance(changes[0], list) and len(changes[0]) > 1:
                # Multi-line edit
                current_lines = cell_contents_buffer.get(cell_index, "").split('\n') if cell_contents_buffer.get(cell_index) else [""]
                start_pos = changes[0][0]
                new_content = changes[0][1:]
                
                # Expand lines if needed
                while len(current_lines) <= start_pos:
                    current_lines.append("")
                
                # Replace content
                current_lines[start_pos:start_pos+1] = new_content
                cell_contents_buffer[cell_index] = '\n'.join(current_lines)
            elif changes and len(changes) >= 2:
                # Character-by-character edit
                line_index = changes[0]
                char_changes = changes[1]
                if isinstance(char_changes, list) and len(char_changes) == 2:
                    pos, char = char_changes
                    current_lines = cell_contents_buffer.get(cell_index, "").split('\n') if cell_contents_buffer.get(cell_index) else [""]
                    
                    # Expand lines if needed
                    while len(current_lines) <= line_index:
                        current_lines.append("")
                    
                    # Expand characters in line if needed
                    current_line = current_lines[line_index]
                    while len(current_line) <= pos:
                        current_line += " "
                    
                    # Replace character
                    current_line = current_line[:pos] + char + current_line[pos+1:]
                    current_lines[line_index] = current_line
                    cell_contents_buffer[cell_index] = '\n'.join(current_lines)
            
        # Cell execution
        elif event_name == 'CellExecuteEvent':
            exec_cell_index = event_info.get('cells', [{}])[0].get('index')
            cell_content_from_log, cell_output = get_executed_cell_contents(exec_cell_index, log.get('notebookState'))
            
            # Check if there was manual editing before execution
            actual_content = cell_content_from_log.strip()
            
            # Check if content changed from last assistant insertion
            last_assistant = last_assistant_content.get(exec_cell_index, "").strip()
            
            should_log_manual_edit = False
            
            if last_assistant and actual_content != last_assistant:
                # Content changed from what assistant inserted - this is a manual edit
                should_log_manual_edit = True
            elif not last_assistant:
                # No assistant content, check buffer comparison
                buffer_content = cell_contents_buffer.get(exec_cell_index, "").strip()
                should_log_manual_edit = buffer_content and buffer_content != actual_content
            
            if should_log_manual_edit:
                event_dict.append(OrderedDict({
                    'event': 'Edited cell',
                    'notebook': notebook_path,
                    'time': event_time_str,
                    'cell_index': exec_cell_index,
                    'content': actual_content
                }))
            
            # Reset tracking for this cell after execution
            cell_contents_buffer.pop(exec_cell_index, None)
            last_assistant_content.pop(exec_cell_index, None)

            # Log the execution event
            if event_info.get('success'):
                event_dict.append(OrderedDict({
                    'event': 'Executed cells',
                    'notebook': notebook_path,
                    'time': event_time_str,
                    'cell_index': exec_cell_index,
                    'input': cell_content_from_log,
                    'output': cell_output
                }))
            else:
                kernel_error = event_info.get('kernelError', {})
                error_name = kernel_error.get('errorName', 'UnknownError')
                error_value = kernel_error.get('errorValue', 'Unknown error')
                event_dict.append(OrderedDict({
                    'event': 'Executed cells with error',
                    'notebook': notebook_path,
                    'time': event_time_str,
                    'cell_index': exec_cell_index,
                    'error': f"{error_name}: {error_value}",
                    'content': cell_content_from_log
                }))

    # Sort events by time
    event_dict.sort(key=lambda x: datetime.strptime(x['time'], '%Y-%m-%d %H:%M:%S'))
    
    # Generate summary events
    for item in event_dict:
        events.append(f"Event: '{item['event']}' at {item['time']} in notebook '{item.get('notebook', 'N/A')}'")

    return events, event_dict


def analyze_logs(log_file_path, chat_log_path, start_time, end_time, filter_automated=True):
    log_data = load_log_file(log_file_path)
    log_summary, log_objects = reconstruct_cell_contents(log_data)
    logs = []
    print(len(log_objects))
    # Load the chat logs
    with open(chat_log_path, 'r') as file:
        chat_data = json.load(file)

    # Convert timestamps
    start_timestamp = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
    end_timestamp = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

    # Filter and print notebook events
    print("Notebook Events:")
    for event in log_objects:
        event_time = datetime.strptime(event['time'], '%Y-%m-%d %H:%M:%S').timestamp()
        if start_timestamp <= event_time <= end_timestamp:
            logs.append(event)
            if event['event'] == 'Executed cells':
                print(event['event'], event['time'], event['input'])
            else:
                print(event)


    print("\nChat Messages:")
    for message in chat_data['messages']:
        message_time = message['time']
        if start_timestamp <= message_time <= end_timestamp:
            if filter_automated and 'automated' in message:
                continue
            # Convert timestamp to string
            message['time'] = datetime.fromtimestamp(message_time).strftime('%Y-%m-%d %H:%M:%S')
            print(message)
        else:
            # Remove the message from the list if it is outside the time range
            chat_data['messages'].remove(message)

    return logs, chat_data
