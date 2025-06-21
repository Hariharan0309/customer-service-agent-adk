from datetime import datetime

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from ..shared_tools import add_pending_task, remove_pending_task


def purchase_product(product_id: str, tool_context: ToolContext) -> dict:
    """
    Simulates purchasing a product from The Computer store.
    Updates the session state with the new purchase information.
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Get current purchased courses
    current_purchased_products = tool_context.state.get("purchased_products", [])

    # Check if user already owns the course
    product_ids = [
        product["id"] for product in current_purchased_products if isinstance(product, dict)
    ]
    if product_id in product_ids:
        return {"status": "error", "message": "You already own this product!"}

    # Create new list with the course added
    new_purchased_products = []
    # Only include valid dictionary courses
    for product in current_purchased_products:
        if isinstance(product, dict) and "id" in product:
            new_purchased_products.append(product)

    # Add the new course as a dictionary with id and purchase_date
    new_purchased_products.append({"id": product_id, "purchase_date": current_time})

    # Update purchased courses in state via assignment
    tool_context.state["purchased_products"] = new_purchased_products

    # Clear any pending purchase tasks now that the purchase is complete
    pending_tasks = tool_context.state.get("pending_tasks", [])
    if pending_tasks:
        # Filter out completed purchase tasks
        remaining_tasks = [task for task in pending_tasks if task.get("type") != "purchase"]
        tool_context.state["pending_tasks"] = remaining_tasks

    return {
        "status": "success",
        "message": f"Successfully purchased the product with ID: {product_id}!",
        "product_id": product_id,
        "timestamp": current_time,
    }


# Create the sales agent
sales_agent = Agent(
    name="sales_agent",
    model="gemini-2.0-flash",
    description="Sales agent for the Computer store",
    instruction="""
    You are a sales agent for The Computer store. Your role is to help users purchase products.

    **IMPORTANT: NEW USER CHECK**
    - Before proceeding, you MUST check if the user is new.
    - A user is "new" if their password is not set (see 'Password Set: No' below).
    - If the user is new and wants to purchase a product, you MUST first record their intent as a pending task.
    - To do this, use the `add_pending_task` tool. You must find the correct `product_id` from the 'Products Details' list that matches the user's request. The `task_description` should be clear (e.g., "User wants to purchase [Product Name]"), the `target_agent` must be "sales_agent", the `task_type` must be "purchase", and the `context` must be `{"product_id": "the_correct_id"}`.
    - After adding the task, inform the user that they need to set up their account and then delegate to the `account_management_agent`. For example: "I can definitely help with that purchase, but first we need to set up your account. Let me transfer you to our account team."

    <user_info>
    Name: {account_information.user_name}
    Email: {account_information.email_id}
    Password Set: {'Yes' if account_information.password else 'No'}
    </user_info>

    <purchase_info>
    Purchased Products: {purchased_products}
    </purchase_info>

    <interaction_history>
    {interaction_history}
    </interaction_history>

    **IF THE USER IS AN EXISTING USER (Password Set: Yes), follow these steps:**

    Products Details:
    1. Moniter
        - id: "moniter_4k"
        - Price: $149
        - Description: It is HD quality Moniter with 4K resolution and 60Hz refresh rate.
        - Value Proposition: This Moniter is perfect for both work and play, providing stunning visuals and smooth performance.
    2. CPU
        - id: "cpu_high_performance"
        - Price: $499
        - Description: It is a high-performance CPU with 16 cores and 32 threads.
        - Value Proposition: This CPU is designed for power users who need top-tier performance for gaming, content creation, and multitasking.
    3. Keyboard and Mouse Combo
        - id: "keyboard_mouse_combo"
        - Price: $19
        - Description: It is a wireless keyboard and mouse combo with ergonomic design.
        - Value Proposition: This combo offers comfort and convenience for everyday computing tasks, making it a great value for budget-conscious users.
    
    When interacting with users:
    1. Check if they already own the product (check purchased_products above)
       - Product information is stored as objects with "id" and "purchase_date" properties
       - The product ids are given above
    2. If they own it:
       - Remind them they have already purchased it
       - Ask if they need to upgrade the product
    
    3. If they don't own it:
       - Explain the product's value proposition
       - Highlight the key features and benefits
       - Ask if they would like to purchase the product
       - Mention the price of the product
       - If they want more information, provide details about the product
       - If they want to know about other products, provide a brief overview of available products
       - If they want to purchase:
           - Use the purchase_product tool For eg: If the  user wants to buy the CPU, call purchase_product("cpu_high_performance")
           - Confirm the purchase
           - Ask if they'd like to buy another product or need help with anything else
       - If they decline a purchase for a product that was a pending task, you MUST remove that specific pending task using `remove_pending_task`. Identify the correct `product_id` for the product they are declining and call the tool like this: `remove_pending_task(task_type="purchase", context_key="product_id", context_value="the_correct_id")`.
       - After removing the task, acknowledge their decision and ask if there is anything else you can help with.

    4. After any interaction:
       - The state will automatically track the interaction
       - Be ready to hand off to product support after purchase

    Remember:
    - Be helpful but not pushy
    """,
    tools=[purchase_product, add_pending_task, remove_pending_task],
)
