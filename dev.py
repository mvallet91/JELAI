
import os
import json
import time

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnablePassthrough
from langchain_community.llms import Ollama
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(".env"))

st = time.time()

chat = ChatOpenAI(model="gpt-3.5-turbo-1106")
ollama = Ollama(
    base_url=os.getenv('base_url'),
    model="codegemma:7b-instruct"
)

demo_ephemeral_chat_history = ChatMessageHistory()

# demo_ephemeral_chat_history.add_user_message("Hey there! I'm Nemo.")
# demo_ephemeral_chat_history.add_ai_message("Hello!")
# demo_ephemeral_chat_history.add_user_message("How are you today?")
# demo_ephemeral_chat_history.add_ai_message("Fine thanks!")

print("Time to initialize:", time.time() - st)
# load the chat history
with open("./ChatPandas.chat", "r") as f:
    full_chat = f.read()
chat_contents = json.loads(full_chat)

for message in chat_contents["messages"][-10:]:
    if message["sender"] == "ccd4593782e34cc5ae31e54ba3684597":
        demo_ephemeral_chat_history.add_user_message(message["body"])
    else:
        demo_ephemeral_chat_history.add_ai_message(message["body"])
print("Time to load the chat history: ", time.time() - st)


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful Data Science assistant embedded in a Jupyter Notebook (using Python 3.11, Pandas, Matplotlib and Seaborn, latest version 2024). Be informative and concise. Answer all questions to the best of your ability. Use the provided chat history for context, no need to mention it.",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
    ]
)

# chain = prompt | chat
chain = prompt | ollama


chain_with_message_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: demo_ephemeral_chat_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

def summarize_messages(chain_input):
    stored_messages = demo_ephemeral_chat_history.messages
    if len(stored_messages) == 0:
        return False
    summarization_prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="chat_history"),
            (
                "system",
                """
                Distill the above chat messages into a single summary message that will be used for an LLM agent to continue the conversation. It must be readable for an LLM, not a human. 
                We have a very tight limit on tokens, compress it as much as possible while allowing the agent to continue the flow of the conversation. Focus on spoecific concepts mentioned.
                """,
            ),
        ]
    )
    summarization_chain = summarization_prompt | ollama

    summary_message = summarization_chain.invoke({"chat_history": stored_messages})

    demo_ephemeral_chat_history.clear()

    demo_ephemeral_chat_history.add_message(summary_message)

    return True


config = {"configurable": {"session_id": "abc20"}}

print("Time to create the chain: ", time.time() - st)
chain_with_summarization = (
    RunnablePassthrough.assign(messages_summarized=summarize_messages)
    | chain_with_message_history
)
print("Time to create the chain with summarization: ", time.time() - st)

# chain_with_summarization.invoke(
#     {"input": "What did I say my name was?"},
#     config=config
# )

# chain_with_summarization.invoke(
#     {"input": "I love ice cream!"},
#     config=config
# )

chain_with_summarization.invoke(
    {"input": "How can I compare 2 datasets in there?"},
    config=config
)
print("Time to invoke the chain: ", time.time() - st)


print(demo_ephemeral_chat_history.messages)