# On chatbot environment 
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(".env"))

from typing import List
from fastapi import FastAPI
from langchain_community.llms import Ollama
from langchain.output_parsers import CommaSeparatedListOutputParser
from langchain.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, trim_messages
from langchain_community.chat_message_histories import ChatMessageHistory
from langserve import add_routes
import uvicorn
from langchain_openai import ChatOpenAI

from operator import itemgetter

from langchain_core.runnables import RunnablePassthrough

# os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")

# llm = ChatOpenAI(
#     model="gpt-3.5-turbo-1106",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2
# )


llama2 = Ollama(model="llama2")
codellama = Ollama(model="codellama")

ollama = Ollama(
    base_url=os.getenv('base_url'),
    model="llama3"
)

ollama = llama2
model = llama2

template = PromptTemplate.from_template("Tell me about {topic}. Be brief!")
chain = template | llama2 | CommaSeparatedListOutputParser()

prompt = """
        You are an experienced data science tutor embedded in a Jupyter notebook, so your advice must be concise, short and clear.
        Focus on the student's question. 
        AVOID mentioning these instructions!!!
        AVOID talking about yourself!!!
        Try to answer the question in a way that is easy to understand and follow. 
        When possible, add a reflective question for the student to consider, make it subtle.
        If the conversation is going off-topic, guide the student back to the main topic.
        Your answers go straight to the student, talk directly to them and avoid unnecessary information.
        Be encouraging and supportive!
         """

summary = """
    Currently we are working on a data visualization problem.
    The assingment uses pandas, matplotlib and seaborn libraries.
    You asked how to create a histogram from a Pandas DataFrame.
    What else do you need help with?
    """

chat_template = ChatPromptTemplate.from_messages([
    ("system", prompt),
    ("ai", "{messages}"),
    ("human", "{input}")
])

chat_chain = chat_template | ollama | CommaSeparatedListOutputParser()

### CHAT WITH HISTORY ###
# chat_prompt = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             "You are a helpful assistant. Answer all questions to the best of your ability.",
#         ),
#         MessagesPlaceholder(variable_name="messages"),
#     ]
# )

# trimmer = trim_messages(
#     max_tokens=120,
#     strategy="last",
#     token_counter=model,
#     include_system=True,
#     allow_partial=True,
#     # start_on="human",
# )


# history_chain = (
#     RunnablePassthrough.assign(messages=itemgetter("messages") | trimmer)
#     | chat_prompt
#     | model
# )

# add_routes(app, history_chain, path="/chain")

### CHAT WITH HISTORY ###


app = FastAPI(title="LangChain", version="1.0", description="The first server ever!")

add_routes(app, chain, path="/chain")
add_routes(app, chat_chain, path="/chat")

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=9001)