import os.path
import base64
import email
import json # Import the json module
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup # Import BeautifulSoup for HTML parsing

# If modifying these scopes, delete the file token.json.
# 'https://www.googleapis.com/auth/gmail.readonly' allows reading all messages and their metadata.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail_api():
    """
    Authenticates with the Gmail API, handling OAuth 2.0 flow.
    It checks for an existing token.json, refreshes it if needed,
    or performs a new authentication flow.
    Returns:
        google.oauth2.credentials.Credentials: Authenticated credentials.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            try:
                creds.refresh(InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES))
            except Exception as e:
                print(f"Error refreshing token: {e}. Please re-authenticate.")
                # Fallback to new flow if refresh fails
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            print("No valid token found. Initiating new authentication flow...")
            # Use 'credentials.json' downloaded from Google Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def list_recent_messages(service, max_results=10):
    """
    Lists recent email subjects and senders.
    Args:
        service: Authenticated Gmail API service object.
        max_results (int): Maximum number of messages to list.
    Returns:
        list: A list of dictionaries, each containing 'id', 'sender', and 'subject'.
    """
    messages_data = []
    try:
        # Call the Gmail API to get a list of messages
        results = service.users().messages().list(userId='me', maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            print('No messages found.')
            return []

        print(f'\nRecent {max_results} Emails:')
        print('----------------------------------------------------')
        for i, message in enumerate(messages):
            msg = service.users().messages().get(userId='me', id=message['id'], format='metadata').execute()
            headers = msg['payload']['headers']
            
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'N/A')
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'N/A')
            
            print(f'{i + 1}. From: {sender} | Subject: {subject}')
            messages_data.append({'id': message['id'], 'sender': sender, 'subject': subject})
        print('----------------------------------------------------')
        return messages_data

    except HttpError as error:
        print(f'An HTTP error occurred: {error}')
        return []

def get_message_content(service, msg_id):
    """
    Retrieves and decodes the full content of a specific email message,
    and extracts sender, receiver, subject, and message body.
    Args:
        service: Authenticated Gmail API service object.
        msg_id (str): The ID of the message to retrieve.
    Returns:
        dict: A dictionary containing 'sender_email', 'receiver_email', 'subject', and 'message_body',
              or None if an error occurs or content cannot be extracted.
    """
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        # Initialize variables for email details
        sender_email = 'N/A'
        receiver_email = 'N/A'
        subject = 'N/A'
        email_body_plain = "" # Changed to accumulate plain text only

        # Extract headers
        headers = msg['payload']['headers']
        for h in headers:
            if h['name'] == 'From':
                sender_email = h['value']
            elif h['name'] == 'To':
                receiver_email = h['value']
            elif h['name'] == 'Subject':
                subject = h['value']
        
        # Decode the message payload
        payload = msg['payload']
        parts = payload.get('parts', [])

        # Helper to extract plain text from parts, prioritizing plain over HTML
        def find_and_decode_text_part(parts_list):
            plain_text = ""
            html_text = ""

            for part in parts_list:
                mime_type = part.get('mimeType')
                if 'data' in part['body']:
                    data = part['body']['data']
                    decoded_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if mime_type == 'text/plain':
                        plain_text += decoded_data + "\n" # Accumulate all plain text parts
                    elif mime_type == 'text/html':
                        html_text += decoded_data + "\n" # Accumulate all HTML parts
                elif 'parts' in part:
                    # Recursively search in nested parts
                    nested_plain, nested_html = find_and_decode_text_part(part['parts'])
                    plain_text += nested_plain
                    html_text += nested_html
            return plain_text, html_text

        # First, try to get plain text from the parts
        extracted_plain_from_parts, extracted_html_from_parts = find_and_decode_text_part(parts)
        
        if extracted_plain_from_parts:
            email_body_plain = extracted_plain_from_parts
        elif extracted_html_from_parts:
            # If only HTML parts are found, strip HTML to get plain text
            soup = BeautifulSoup(extracted_html_from_parts, 'html.parser')
            email_body_plain = soup.get_text(separator='\n') # Get text with newlines for better readability
        
        # Fallback for simpler messages if body is not extracted from parts, but raw exists
        if not email_body_plain and 'raw' in msg:
            raw_msg = base64.urlsafe_b64decode(msg['raw']).decode('utf-8', errors='ignore')
            parsed_email = email.message_from_string(raw_msg)
            
            raw_plain_text = ""
            raw_html_text = ""

            for part in parsed_email.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))

                if 'attachment' not in cdispo: # Ignore attachments
                    if ctype == 'text/plain':
                        raw_plain_text += part.get_payload(decode=True).decode('utf-8', errors='ignore') + "\n"
                    elif ctype == 'text/html':
                        raw_html_text += part.get_payload(decode=True).decode('utf-8', errors='ignore') + "\n"
            
            if raw_plain_text:
                email_body_plain = raw_plain_text
            elif raw_html_text:
                # If only raw HTML is found, strip it
                soup = BeautifulSoup(raw_html_text, 'html.parser')
                email_body_plain = soup.get_text(separator='\n')

        email_data = {
            "sender_email": sender_email,
            "receiver_email": receiver_email,
            "subject": subject,
            "message_body": email_body_plain.strip() # Remove leading/trailing whitespace
        }
        return email_data

    except HttpError as error:
        print(f'An HTTP error occurred: {error}')
        return None
    except Exception as e:
        print(f"An error occurred during message content extraction: {e}")
        return None

def main():
    """Shows basic usage of the Gmail API."""
    try:
        creds = authenticate_gmail_api()
        service = build('gmail', 'v1', credentials=creds)

        # List recent messages
        messages = list_recent_messages(service)

        if messages:
            while True:
                try:
                    choice = input("\nEnter the number of the email you want to read (or 'q' to quit): ")
                    if choice.lower() == 'q':
                        break
                    
                    idx = int(choice) - 1
                    if 0 <= idx < len(messages):
                        selected_message_id = messages[idx]['id']
                        print(f"Fetching full details for email from '{messages[idx]['sender']}' with subject: '{messages[idx]['subject']}'")
                        
                        email_data = get_message_content(service, selected_message_id)
                        
                        if email_data:
                            print('\n--- Email Details (JSON Format) ---')
                            print(json.dumps(email_data, indent=4))
                            print('----------------------------------------------------')
                        else:
                            print("Could not retrieve full details for the selected email.")
                    else:
                        print("Invalid number. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter a number or 'q'.")
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")
        else:
            print("No messages to display or access.")

    except HttpError as error:
        print(f'An HTTP error occurred: {error}')
    except Exception as e:
        print(f"An overall error occurred: {e}")

if __name__ == '__main__':
    main()
