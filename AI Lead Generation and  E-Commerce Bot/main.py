import os
import json
import chainlit as cl
from agents import Agent, Runner, SQLiteSession, function_tool
from openai.types.responses import ResponseTextDeltaEvent
from tools import web_search ,products,book_order,admin_update_order_status,check_order_status
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from agents import ModelSettings, RunConfig, OpenAIChatCompletionsModel, set_tracing_disabled
from openai import AsyncOpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

load_dotenv()
set_tracing_disabled(True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=client,
)

# Default config for MainAgent
default_config = RunConfig(
    model=model,
    model_provider=client,
    tracing_disabled=True,
    model_settings=ModelSettings(
        temperature=0.7,
        top_p=0.5,
        tool_choice="auto"
    ),
)

# Config for ProductAgent to force products tool
product_config = RunConfig(
    model=model,
    model_provider=client,
    tracing_disabled=True,
    model_settings=ModelSettings(
        temperature=0.7,
        top_p=0.5,
        tool_choice="required"
    ),
)

session = SQLiteSession("ecom_session_1", "conversations.db")




# ---------- Agents ----------
product_agent = Agent(
    name="Product Catalog Agent",
    instructions="""
    You are responsible for handling product catalog queries.
    - Use the `products` tool to access the catalog.
    - If user asks for a product name or type, search the catalog text.
    - Display only matching results.
    - If product not found, politely inform the user.
    - Output results in a neat table-like format (Name | Price | Stock).
    """,
    tools=[products]
)

order_agent = Agent(
    name="Order Booking Agent",
    instructions="""
    You handle customer orders.
    - Collect customer name, contact, address, and desired product.
    - Always extract these four fields:
      1. name
      2. contact
      3. address
      4. product
    - If any field is missing, politely ask the user for it.
    - Once all fields are available, call the `book_order` tool.
    - If customer name already exists, reuse stored contact & address.
    - Always confirm the booking with a friendly message and emojis.
    """,
    tools=[book_order]
)

main_agent = Agent(
    name="Main Agent",
    instructions="""
    You are the main assistant for the e-commerce demo.
    - Handle greetings, small talk, and basic product/order conversations.
    - If user asks about products, hand off to Product Catalog Agent.
    - If user wants to place an order, hand off to Order Booking Agent.
    - Keep replies short, friendly, and emoji-rich.
    """,
    handoffs=[product_agent, order_agent],
    tools=[products, book_order,check_order_status,admin_update_order_status]
)

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="🛍️ Show Catalog",
            message="Show me the product catalog."
        ),
        cl.Starter(
            label="🧾 Place Order",
            message="I want to order a Laptop."
        ),
        cl.Starter(
            label="📦 Track Order",
            message="Check order status for ID 1"
        ),
        cl.Starter(
            label="👨‍💼 Admin Update",
            message="Update order ID 1 to Delivered successfully"
        ),
        cl.Starter(
            label="🔎 Search Product",
            message="Find me a smartphone under 100k."
        ),
    ]

@cl.on_message
async def handle_message(message: cl.Message):
    msg = cl.Message(content="🤔 Thinking...⏳")
    await msg.send()
    
    # Determine which agent to use
    agent = main_agent
    config = default_config
    if any(keyword in message.content.lower() for keyword in ["product", "catalog", "items", "stock"]):
        agent = product_agent
        config = product_config
    
    response = Runner.run_streamed(
        agent,
        input=message.content,
        session=session,
        run_config=config,
    )

    async for event in response.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            await msg.stream_token(event.data.delta)
    msg.content = response.final_output
    await msg.update()