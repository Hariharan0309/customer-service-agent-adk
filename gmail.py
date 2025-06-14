import os.path
import base64
import email
import json # Import the json module
from email.mime.text import MIMEText # Import MIMEText for creating email messages
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup # Import BeautifulSoup for HTML parsing


# If modifying these scopes, delete the file token.json.
# 'https://www.googleapis.com/auth/gmail.send' allows sending messages.
# This scope implicitly allows reading headers and subjects for drafts,
# but for full read access, 'gmail.readonly' or 'gmail.modify' would be needed.
# Since the user asked for read and send, gmail.send is sufficient for the sending part.
# For full read and send capability, 'https://www.googleapis.com/auth/gmail.compose' or 'https://www.googleapis.com/auth/gmail.modify' is generally used.
# However, for just sending, 'gmail.send' is less permissive.
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify'] # Added gmail.modify to keep read/unread functionality

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
                # Ensure the flow is initialized with the correct scopes for refresh
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds.refresh(flow.credentials)
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

def mark_message_as_read(service, msg_id):
    """
    Marks a specific message as read by removing the 'UNREAD' label.
    Args:
        service: Authenticated Gmail API service object.
        msg_id (str): The ID of the message to mark as read.
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Message {msg_id} marked as read.")
        return True
    except HttpError as error:
        print(f'An HTTP error occurred when marking as read: {error}')
        return False
    except Exception as e:
        print(f"An error occurred while marking message as read: {e}")
        return False

def read_unread_emails_one_by_one(service):
    """
    Fetches unread emails one by one, displays their content, and marks them as read.
    Args:
        service: Authenticated Gmail API service object.
    """
    try:
        # Fetch unread messages
        results = service.users().messages().list(userId='me', q='is:unread').execute()
        messages = results.get('messages', [])

        if not messages:
            print('\nNo unread messages found.')
            return

        print(f'\nFound {len(messages)} unread email(s). Processing one by one:')
        print('----------------------------------------------------')
        
        for i, message in enumerate(messages):
            msg_id = message['id']
            print(f"\n--- Processing Unread Email {i + 1}/{len(messages)} ---")
            
            # Get email content
            email_data = get_message_content(service, msg_id)
            
            if email_data:
                print(json.dumps(email_data, indent=4))
                
                # Ask user if they want to mark as read
                action = input("\nMark this email as read? (y/n, default: y): ").lower()
                if action == 'n':
                    print("Email left as unread.")
                else:
                    mark_message_as_read(service, msg_id)
            else:
                print(f"Could not retrieve content for unread message ID: {msg_id}")
            
            if i < len(messages) - 1:
                input("\nPress Enter to process the next unread email...")
        
        print('\n----------------------------------------------------')
        print('Finished processing unread emails.')

    except HttpError as error:
        print(f'An HTTP error occurred: {error}')
    except Exception as e:
        print(f"An overall error occurred during unread email processing: {e}")

def create_message_and_send(service, sender_email, to_email, subject, message_text):
    """
    Creates an email message and sends it.
    Args:
        service: Authenticated Gmail API service object.
        sender_email (str): The email address of the sender ('me' is recommended).
        to_email (str): The email address of the recipient.
        subject (str): The subject of the email.
        message_text (str): The plain text content of the email.
    Returns:
        dict: The sent message object if successful, None otherwise.
    """
    try:
        message = MIMEText(message_text)
        message['to'] = to_email
        message['from'] = sender_email # Use 'me' for the authenticated user
        message['subject'] = subject

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        print(f"\nEmail sent successfully! Message ID: {sent_message['id']}")
        return sent_message
    except HttpError as error:
        print(f'An HTTP error occurred while sending email: {error}')
        return None
    except Exception as e:
        print(f"An error occurred while creating/sending message: {e}")
        return None

