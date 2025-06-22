
# AI-Powered Customer Service Agent Team

This project implements a sophisticated, multi-agent customer service system built using the `Google Agent Development Kit (ADK)`. The system processes incoming emails from users, understands their intent, and routes their requests to a team of specialized AI agents, each designed to handle a specific aspect of customer service.

The architecture is designed to be robust, handling everything from initial user account setup and sales inquiries to post-purchase support, order management, and administrative tasks.

## Architecture Overview

The system operates on a hierarchical agent model, with a central `Manager Agent` acting as a smart router.

1. **Email Processing**: The `main.py` script continuously monitors a Gmail inbox for unread emails.
2. **Session Management**: When a new email arrives, the system creates or retrieves a persistent user session from a SQLite database (`my_agent_data.db`), tracking the user's entire interaction history and state.
3. **Manager Agent Delegation**: The user's query is passed to the `Manager Agent`, which follows a strict set of rules to delegate the task to the most appropriate sub-agent.
4. **Sub-Agent Execution**: The specialized sub-agent performs its task, using its unique tools to interact with the database or modify the user's state.
5. **State Persistence**: All changes and interactions are saved back to the user's session in the database.

## Installation

To set up the project environment, you can use Conda with the provided `environment.yml` file.

```bash
# 1. Clone the repository
git clone https://github.com/Hariharan0309/customer-service-agent-adk.git
cd customer-service-agent-adk

# 2. Create and activate the Conda environment from the environment.yml file
conda env create -f environment.yml
conda activate customer-service-agent

```

## Set up Google Cloud authentication

Follow the instructions to enable the Gmail API and download your credentials.json file.
Place the credentials.json file in the root directory of the project.

## 📩 Generating Gmail OAuth credentials.json

To allow the application to read and respond to emails using the Gmail API, you need to create and download a credentials.json file from Google Cloud. Here's how:

1. Go to the Google Cloud Console.
2. Create a new project (or select an existing one).
3. In the sidebar, go to “APIs & Services” → “Library”.
4. Search for “Gmail API” and click Enable.
5. Next, go to “APIs & Services” → “Credentials”.
6. Click “+ CREATE CREDENTIALS” → “OAuth client ID”.
    - If prompted, first configure the OAuth consent screen:
      - Choose "External" user type (if you're testing it yourself).
      - Fill in required fields (App name, email, etc.)
      - Save and continue.
7. Once on the OAuth Client ID creation page:
    - Select Application type: Desktop App
    - Name it (e.g., "Customer Service Agent Desktop Client") and click Create.
8. A modal will appear with your client ID details — click Download JSON.
9. Rename the file to credentials.json and place it in the root directory of the project.

Once the installation is complete and you have authenticated, simply run the main script:

```bash
python main.py
```

The application will start monitoring the associated Gmail account for unread emails and process them as they arrive.

## Agents and Features

The core of the system is its team of specialized agents, orchestrated by the Manager Agent.

### 1. 🧭 Manager Agent

The central nervous system of the project. It does not answer users directly but analyzes every incoming query and delegates it to the correct sub-agent based on a strict routing tree. It handles admin checks, new user onboarding, and task handoffs between agents.

### 2. 🔐 Admin Agent

A powerful agent with privileged access, activated only when the query comes from the designated admin email (<admin@gmail.com>) .

- View all users and their complete session states.
- Update the status of any order (e.g., from "dispatched" to "delivered").
- Add or delete support staff members from the database.
- Clear a user's support staff assignment once their issue is resolved.
- Clear a user's interaction history.
- All modification actions are protected by an admin password.

### 3. 👤 Account Management Agent

Handles all user account-related tasks.

- Guides new users through setting an initial password and phone number.
- Allows existing users to update their password or phone number after verification.

### 4. 🛒 Sales Agent

Manages the product catalog and new purchases.

- Provides detailed information about products, including price and value proposition.
- Retrieves and displays average user feedback ratings for products before purchase.
- Processes new product purchases, generating a unique order_id for each transaction.
- Handles users wanting to buy a product they already own.
- Creates "pending tasks" for new users who want to buy something, ensuring their request is remembered after they complete account setup.

### 5. 📦 Order Agent

Manages all post-purchase inquiries for existing orders.

- Checks and reports order status ("dispatched" or "delivered").
- Calculates and provides an estimated delivery date (2 days from purchase).
- Allows users to cancel an order if it has not yet been delivered.
- Processes product returns or exchanges within 30 days of the purchase date.

### 6. 🛠️ Support Agent

Provides technical support for products the user has purchased.

- Accesses a built-in knowledge base to provide troubleshooting steps for common problems.
- Verifies that a user owns a product before providing support.
- Can escalate an unresolved issue to the Handoff Agent.

### 7. ⭐ Feedback Agent

Gathers customer feedback to improve the service and inform other users.

- At the end of a conversation, it asks the user to rate a product they've purchased on a scale of 1-5.
- It intelligently checks which products a user has not yet rated to avoid asking for the same feedback twice.
- Stores all feedback in the database.

### 8. 📞 Handoff Agent

Manages the escalation process from an AI agent to a human support specialist.

- When an issue is escalated by the Support Agent, it assigns a free human support staff member from the database to the user's case.
- It updates the user's session state with the assigned specialist's name, preventing other agents from trying to handle the same issue.

## 🤝 Contributing

State if you are open to contributions and what your requirements are for accepting them.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE.txt` for more information.

## 📬 Contact

Hariharan R - <hariharan2002psg@gmail.com>
