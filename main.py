from gmail import authenticate_gmail_api, list_recent_messages, get_message_content, read_unread_emails_one_by_one, create_message_and_send
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
"""
This script provides a command-line interface to interact with the Gmail API.
It allows users to list recent emails, read unread emails one by one, and send new emails.
"""

def main():
    """Shows basic usage of the Gmail API."""
    try:
        creds = authenticate_gmail_api()
        service = build('gmail', 'v1', credentials=creds)

        while True:
            print("\nChoose an option:")
            print("1. List recent emails (first 10)")
            print("2. Read unread emails one by one and mark as read")
            print("3. Write and send an email")
            print("q. Quit")
            
            choice = input("Enter your choice: ").lower()

            if choice == '1':
                messages = list_recent_messages(service)
                if messages:
                    while True:
                        try:
                            sub_choice = input("\nEnter the number of the email you want to read (or 'b' to go back to main menu): ")
                            if sub_choice.lower() == 'b':
                                break
                            
                            idx = int(sub_choice) - 1
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
                            print("Invalid input. Please enter a number or 'b'.")
                        except Exception as e:
                            print(f"An unexpected error occurred: {e}")
            elif choice == '2':
                read_unread_emails_one_by_one(service)
            elif choice == '3':
                print("\n--- Send a New Email ---")
                to_email = input("To (recipient's email): ")
                subject = input("Subject: ")
                message_body = input("Message body: ")
                
                # The 'From' address will automatically be the authenticated user's email if 'userId' is 'me'
                # It's good practice to display 'me' for clarity.
                sender_email = 'me' # The authenticated user will be the sender
                
                create_message_and_send(service, sender_email, to_email, subject, message_body)
            elif choice == 'q':
                print("Exiting application.")
                break
            else:
                print("Invalid choice. Please try again.")

    except HttpError as error:
        print(f'An HTTP error occurred: {error}')
    except Exception as e:
        print(f"An overall error occurred: {e}")

if __name__ == '__main__':
    main()