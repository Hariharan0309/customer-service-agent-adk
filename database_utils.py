import sqlite3
import json
from datetime import datetime # For dummy session data

def get_all_rows_from_db(db_file_path, table_name):
    """
    Connects to an SQLite database and fetches all rows from a specified table.

    Args:
        db_file_path (str): The path to the .db file.
        table_name (str): The name of the table to fetch data from.

    Returns:
        list: A list of tuples, where each tuple represents a row.
              Returns an empty list if the table is empty or an error occurs.
    """
    rows = []
    try:
        with sqlite3.connect(db_file_path) as conn:
            cursor = conn.cursor()

            # Execute a query to select all rows from the table
            # Note: Using f-string for table_name can be an SQL injection risk
            # if table_name comes from an untrusted source.
            # Ensure table_name is validated or comes from a trusted source.
            query = f"SELECT * FROM {table_name}"
            cursor.execute(query)

            # Fetch all rows from the executed query
            rows = cursor.fetchall()

    except sqlite3.Error as e:
        print(f"An error occurred while fetching data: {e}")
    return rows

def add_column_if_not_exists(db_path, table_name, column_name, column_type_def="INTEGER DEFAULT 0"):
    """Adds a column to a table if it doesn't already exist."""
    conn_alter = None
    try:
        conn_alter = sqlite3.connect(db_path)
        cursor_alter = conn_alter.cursor()
        
        # Check if column exists
        cursor_alter.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cursor_alter.fetchall()]
        
        if column_name not in columns:
            cursor_alter.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type_def}")
            conn_alter.commit()
            print(f"Added column '{column_name}' to table '{table_name}'.")
        # else:
        #     print(f"Column '{column_name}' already exists in table '{table_name}'.")
            
    except sqlite3.Error as e:
        # This might happen if the table doesn't exist yet, which is fine if created later by ADK
        # or if there's another issue with the ALTER TABLE command.
        print(f"SQLite error while trying to add column '{column_name}' to '{table_name}': {e}")
    finally:
        if conn_alter:
            conn_alter.close()

def process_unprocessed_events(db_file_path, events_table_name):
    """
    Processes unprocessed events from the events table.
    - Ensures a 'processed' column exists.
    - Fetches events where 'processed' is 0.
    - Parses these events to build an interaction history.
    - Extracts the user_id from the first relevant event.
    - Groups interactions by user_id found in each event row.
    - Marks processed events as 'processed = 1'.
    Returns a dictionary: {user_id_1: [interactions_list_1], user_id_2: [interactions_list_2], ...}
    """
    # Ensure 'processed' column exists in the events table
    add_column_if_not_exists(db_file_path, events_table_name, "processed", "INTEGER DEFAULT 0")

    user_specific_interaction_histories = {} # Stores {user_id: [interactions]}
    db_conn_events = None

    try:
        db_conn_events = sqlite3.connect(db_file_path)
        cursor_events = db_conn_events.cursor()

        # --- Part 1: Process 'events' table ---
        # Fetch only unprocessed events (processed = 0)
        # Assuming 'id' is the primary key of the events table (first column, row_tuple[0])
        cursor_events.execute(f"SELECT * FROM {events_table_name} WHERE processed = 0")
        all_unprocessed_events_data = cursor_events.fetchall()

        if all_unprocessed_events_data:
            print(f"Processing {len(all_unprocessed_events_data)} unprocessed event(s) from table '{events_table_name}'...")
            for row_tuple in all_unprocessed_events_data:
                event_id_to_process = row_tuple[0] # Assuming the first column is the event's PK
                current_event_user_id = None
                try:
                    # Extract user_id for the current event row (column index 2)
                    if len(row_tuple) > 2 and row_tuple[2] is not None:
                        current_event_user_id = row_tuple[2]

                    # Expected indices based on your data structure:
                    # row_tuple[5]: actor (e.g., 'user', 'sales_agent', 'manager_agent')
                    # row_tuple[7]: timestamp
                    # row_tuple[8]: JSON payload string
                    if len(row_tuple) < 9:  # Ensure row has enough elements
                        print(f"Event ID {event_id_to_process}: Row too short, skipping.")
                        continue
                    
                    if not current_event_user_id:
                        print(f"Event ID {event_id_to_process}: Missing user_id in event row, skipping.")
                        continue

                    actor = row_tuple[5]
                    timestamp = row_tuple[7]
                    json_payload_str = row_tuple[8]

                    # Skip if essential data is missing or JSON payload isn't a string
                    if not actor or not timestamp or not json_payload_str or not isinstance(json_payload_str, str):
                        print(f"Event ID {event_id_to_process}: Essential data missing or invalid JSON payload string, skipping.")
                        continue

                    json_payload = json.loads(json_payload_str)
                    
                    message_parts = json_payload.get("parts")
                    if not message_parts or not isinstance(message_parts, list) or not message_parts:
                        print(f"Event ID {event_id_to_process}: No message parts found, skipping.")
                        continue

                    # We are interested in the first part for text messages
                    first_part = message_parts[0]
                    message_text = first_part.get("text")

                    if message_text and isinstance(message_text, str):
                        # Clean up message text: replace newlines with spaces and strip whitespace
                        cleaned_message_text = message_text.replace('\r\n', ' ').replace('\n', ' ').strip()
                        
                        if not cleaned_message_text: # Skip if text becomes empty after cleaning
                            print(f"Event ID {event_id_to_process}: Message text empty after cleaning, skipping.")
                            continue

                        if actor == 'user':
                            user_query_dict = {
                                "action": "user_query",
                                "timestamp": timestamp,
                                "query": cleaned_message_text,
                            }
                            if current_event_user_id not in user_specific_interaction_histories:
                                user_specific_interaction_histories[current_event_user_id] = []
                            user_specific_interaction_histories[current_event_user_id].append(user_query_dict)
                        elif actor != 'user': # Assumes other actors are agents
                            agent_response_dict = {
                                "action": "agent_response",
                                "timestamp": timestamp,
                                "agent": actor, # actor here is the agent_name
                                "response": cleaned_message_text,
                            }
                            if current_event_user_id not in user_specific_interaction_histories:
                                user_specific_interaction_histories[current_event_user_id] = []
                            user_specific_interaction_histories[current_event_user_id].append(agent_response_dict)
                        
                        # Mark this event as processed
                        cursor_events.execute(f"UPDATE {events_table_name} SET processed = 1 WHERE id = ?", (event_id_to_process,))
                        db_conn_events.commit()
                        # print(f"Event ID {event_id_to_process} marked as processed.")
                    else:
                        print(f"Event ID {event_id_to_process}: No valid message text found, skipping.")
                
                except (IndexError, TypeError, json.JSONDecodeError, AttributeError) as e:
                    print(f"Error processing event ID {event_id_to_process}: {e}. Skipping this event.")
                    # Optionally, decide if you want to mark as processed even on error, or leave it.
                    # For now, it's left unprocessed if an error occurs during its parsing.
                    continue
            
            print(f"\nProcessed events and grouped interactions by user_id:")
            for uid, history in user_specific_interaction_histories.items():
                print(f"  User ID: {uid}, Interactions: {len(history)}")
                # for item in history: # Optionally print each item
                #     print(f"    {item}")
        else:
            # This message is shown if the table is empty or an error occurred during fetch.
            print(f"No unprocessed events found in table '{events_table_name}'.")

    except sqlite3.Error as e_main_db:
        print(f"A database error occurred during events processing: {e_main_db}")
    except Exception as e_general_main:
        print(f"A general error occurred during events processing: {e_general_main}")
    finally:
        if db_conn_events:
            db_conn_events.close()
    
    return user_specific_interaction_histories

def update_user_session(db_file_path, sessions_table_name, user_id_to_update, new_history_to_append):
    """
    Updates the session(s) for a given user_id by appending new interaction history.
    - Creates a dummy session table and entry if it doesn't exist (for testing/standalone use).
    - Fetches sessions for the user_id.
    - Appends 'new_history_to_append' to the 'interaction_history' in the session's state.
    """
    if not user_id_to_update or not new_history_to_append:
        if not user_id_to_update:
            print(f"\nSkipping '{sessions_table_name}' update because no user_id was provided.")
        if not new_history_to_append:
            print(f"\nSkipping '{sessions_table_name}' update because no new interaction history was provided.")
        return

    print(f"\nAttempting to update '{sessions_table_name}' for user_id: {user_id_to_update}")
    conn_sessions = None
    try:
        conn_sessions = sqlite3.connect(db_file_path)
        conn_sessions.row_factory = sqlite3.Row # Access columns by name
        cursor_sessions = conn_sessions.cursor()

        # --- Dummy 'sessions' table setup (for testing if it doesn't exist or is empty for the user) ---
        # This schema is based on typical ADK session tables. 'id' is the session_id.
        cursor_sessions.execute(f'''
            CREATE TABLE IF NOT EXISTS {sessions_table_name} (
                id TEXT PRIMARY KEY,
                app_name TEXT,
                user_id TEXT,
                state TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        # Insert a sample session if no session exists for the user_id_to_update
        # This is for demonstration; in a real scenario, sessions would be created by the application.
        cursor_sessions.execute(f"SELECT COUNT(*) FROM {sessions_table_name} WHERE user_id = ?", (user_id_to_update,))
        if cursor_sessions.fetchone()['COUNT(*)'] == 0: # sqlite.Row allows access by name
            sample_session_id = f"sample-session-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            sample_user_name = user_id_to_update.split('@')[0] if isinstance(user_id_to_update, str) and '@' in user_id_to_update else "UnknownUser"
            sample_state = {
                "user_name": sample_user_name,
                "purchased_products": [],
                "interaction_history": [{"action": "system_init", "timestamp": datetime.now().isoformat(), "message": "Initial dummy session state."}]
            }
            cursor_sessions.execute(
                f"INSERT INTO {sessions_table_name} (id, app_name, user_id, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_session_id, 'Memory Agent', user_id_to_update, json.dumps(sample_state), datetime.now().isoformat(), datetime.now().isoformat())
            )
            conn_sessions.commit()
            print(f"Inserted a sample session for user_id '{user_id_to_update}' with session_id '{sample_session_id}'.")
        # --- End of dummy 'sessions' table setup ---

        # Fetch sessions matching the user_id
        cursor_sessions.execute(f"SELECT id, state FROM {sessions_table_name} WHERE user_id = ?", (user_id_to_update,))
        sessions_to_update = cursor_sessions.fetchall()

        if not sessions_to_update:
            print(f"No sessions found in '{sessions_table_name}' for user_id '{user_id_to_update}' to update.")
        else:
            for session_row in sessions_to_update:
                session_id_to_update = session_row['id'] # This is the PK of the sessions table row
                current_state_json = session_row['state']
                
                print(f"Processing update for session_id: {session_id_to_update}")
                try:
                    state_dict = json.loads(current_state_json)
                    session_interaction_history = state_dict.get("interaction_history", [])
                    
                    session_interaction_history.extend(new_history_to_append) # Append events history
                    state_dict["interaction_history"] = session_interaction_history
                    
                    updated_state_json = json.dumps(state_dict)
                    
                    cursor_sessions.execute(
                        f"UPDATE {sessions_table_name} SET state = ? WHERE id = ?",
                        (updated_state_json, session_id_to_update)
                    )
                    conn_sessions.commit()
                    print(f"Successfully updated session_id '{session_id_to_update}' with merged interaction history.")
                except json.JSONDecodeError as je:
                    print(f"Error decoding JSON state for session_id '{session_id_to_update}': {je}. State: {current_state_json[:200]}...") # Print part of state
                except Exception as e_update:
                    print(f"Error updating session_id '{session_id_to_update}': {e_update}")
    except sqlite3.Error as e_sess_db:
        print(f"SQLite error with '{sessions_table_name}' table: {e_sess_db}")
    except Exception as e_general: # Catch any other unexpected errors
        print(f"A general error occurred during '{sessions_table_name}' processing: {e_general}")
    finally:
        if conn_sessions:
            conn_sessions.close()

if __name__ == '__main__':
    # Configuration
    database_file = 'my_agent_data.db'
    events_table = 'events'
    sessions_table = 'sessions'

    # Step 1: Process unprocessed events
    print("--- Starting Event Processing ---")
    # process_unprocessed_events now returns a dictionary: {user_id: [interactions]}
    all_new_user_interactions = process_unprocessed_events(database_file, events_table)

    # Step 2: Update user sessions with their respective new interactions
    if all_new_user_interactions:
        print(f"\n--- Starting Session Updates for {len(all_new_user_interactions)} user(s) ---")
        for user_id, new_interactions_for_user in all_new_user_interactions.items():
            if new_interactions_for_user: # Ensure there's actually history to append
                update_user_session(database_file, sessions_table, user_id, new_interactions_for_user)
            else:
                print(f"No new interactions to append for user_id: {user_id}, skipping session update for this user.")
    else:
        print("\nNo new user interactions found in events, skipping all session updates.")
    
    print("\n--- Database processing finished ---")


    
