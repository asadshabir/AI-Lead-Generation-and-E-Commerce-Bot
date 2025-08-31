import os
import json
from agents import function_tool
from openai.types.responses import ResponseTextDeltaEvent
from PyPDF2 import PdfReader
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from ddgs import DDGS

@function_tool
def web_search(query: str) -> str:
    """Fetch latest info from DuckDuckGo search."""
    try:
        with DDGS() as ddgs:
            results = [r["body"] for r in ddgs.text(query, max_results=3)]
        return "\n".join(results)
    except Exception as e:
        return f"❌ Web search failed: {e}"


# ---------- Product Tool ----------
@function_tool
def products():
    """
    Extract raw product catalog text from 'products.pdf' using PyPDF2.
    Always return products as a string wrapped inside a dictionary.
    """
    file_path = "products.pdf"

    if not os.path.exists(file_path):
        return {"products": "⚠️ Error: 'products.pdf' not found in the current directory."}

    try:
        reader = PdfReader(file_path)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
            else:
                text += "⚠️ No text extracted from this page.\n"

        return {"products": text.strip() or "⚠️ No text could be extracted from the PDF."}

    except Exception as e:
        return {"products": f"❌ Error reading 'products.pdf': {str(e)}"}





@function_tool
def book_order(name: str, contact: str, address: str, product: str):
    """
    Book an order by saving user details and product info into orders.json.
    If the user already exists, append order to their history.
    Auto-generate incremental order IDs and send email on new order.
    """

    file_path = "orders.json"
    orders = []

    # Load existing orders
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                orders = json.load(f)
            except json.JSONDecodeError:
                orders = []

    # ✅ Get next order ID
    max_id = 0
    for o in orders:
        for order in o.get("orders", []):
            if "id" in order and isinstance(order["id"], int):
                max_id = max(max_id, order["id"])
    new_order_id = max_id + 1

    # New order entry
    order_entry = {
        "id": new_order_id,
        "product": product,
        "delivery_status": "Pending"
    }

    # Check if user already exists
    user = next((o for o in orders if o["name"].lower() == name.lower()), None)

    if user:
        # append new order
        user["orders"].append(order_entry)
    else:
        # create new user with first order
        new_user = {
            "name": name,
            "contact": contact,
            "address": address,
            "orders": [order_entry]
        }
        orders.append(new_user)

    # Save back to file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=4)

    # ✅ Send email notification for new order
    try:
        sender_email = "asadshabir505@gmail.com"
        receiver_email = "monkeyquest.ai@gmail.com"
        password = "doeqgaztlxkduwyg"

        subject = f"📦 New Order Received - ID {new_order_id}"
        body = f"""
        A new order has been placed!

        Order ID: {new_order_id}
        Name: {name}
        Contact: {contact}
        Address: {address}
        Product: {product}
        Status: Pending ✅
        """

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = receiver_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            server.send_message(msg)

    except Exception as e:
        print(f"⚠️ Email not sent: {e}")

    return {"message": f"Order #{new_order_id} for {product} booked successfully for {name}. Delivery status: Pending ✅"}


@function_tool
def check_order_status(name: str = "", contact: str = "", order_id: int = 0):
    """
    Check order status using any one of (order_id, name, contact).

    Args:
        name (str): Customer's name (optional).
        contact (str): Customer's contact number (optional).
        order_id (int): Order ID (optional).

    Returns:
        dict: Order status message.
    """

    file_path = "orders.json"
    orders = []

    # Load existing orders
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                orders = json.load(f)
            except json.JSONDecodeError:
                orders = []
    else:
        return {"message": "No orders found yet."}

    user = None

    # 1. Check by order ID
    if order_id:
        for u in orders:
            for o in u["orders"]:
                if o["id"] == order_id:
                    user = {"name": u["name"], "contact": u["contact"], "order": o}
                    break

    # 2. If not found, check by name
    if not user and name:
        for u in orders:
            if u["name"].lower() == name.lower():
                if u["orders"]:
                    user = {"name": u["name"], "contact": u["contact"], "order": u["orders"][-1]}
                break

    # 3. If still not found, check by contact
    if not user and contact:
        for u in orders:
            if u["contact"] == contact:
                if u["orders"]:
                    user = {"name": u["name"], "contact": u["contact"], "order": u["orders"][-1]}
                break

    if not user:
        return {"message": "⚠️ Sorry, no matching order found."}

    order = user["order"]
    return {
        "message": (
            f"📦 Order Status:\n"
            f"Order ID: {order.get('id')}\n"
            f"Customer: {user['name']} ({user['contact']})\n"
            f"Product: {order.get('product')}\n"
            f"Delivery Status: {order.get('delivery_status')}"
        )
    }

    

# ✅ Admin secret key (move to .env in production)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

@function_tool
def admin_update_order_status(admin_password: str, order_id: int, new_status: str):
    """
    Update the delivery status of an order by its ID (Admin only).
    Requires correct admin password for authorization.

    Args:
        admin_password (str): Secret admin key.
        order_id (int): The ID of the order to update.
        new_status (str): New delivery status text (e.g., 'Delivered successfully').

    Returns:
        dict: Confirmation message.
    """

    # 🔐 Step 1: Verify password
    if admin_password != ADMIN_PASSWORD:
        return {"message": "❌ Unauthorized! Invalid admin password."}

    file_path = "orders.json"
    if not os.path.exists(file_path):
        return {"message": "⚠️ No orders found."}

    # 🔄 Step 2: Load orders
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            orders = json.load(f)
        except json.JSONDecodeError:
            return {"message": "⚠️ Orders file corrupted."}

    # 📅 Step 3: Append today's date to status
    today = datetime.now().strftime("%Y-%m-%d")
    status_with_date = f"[{today}] {new_status}"

    # 🔍 Step 4: Find and update order by ID
    found = False
    for user in orders:
        for order in user.get("orders", []):
            if order.get("id") == order_id:
                order["delivery_status"] = status_with_date
                found = True
                break

    if not found:
        return {"message": f"⚠️ No order found with ID {order_id}."}

    # 💾 Step 5: Save back
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=4)

    return {"message": f"✅ Order ID {order_id} updated to '{status_with_date}'."}
