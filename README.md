# Learning Analytics-Powered Tutor
## System Architecture
![ds-tutor architecture](./images/DS%20Tutor%20Architecture.png)
<a href="https://www.flaticon.com/free-icons/" title="icons" style="font-size: 0.5em;">Icons created by juicy_fish - Flaticon</a>

### Description
The system consists of a JupyterHub server, individual user Jupyter servers, a chatbot server, and an Ollama server. 
- The JupyterHub server (containerized, running in the `jupyterhub-docker` Docker network) handles user authentication and administration of individual user servers.
- The individual user Jupyter servers are automatically created (or *spawned*) when a user is created in the JupyterHub server (containerized and run in the `jupyterhub-docker` Docker network)
    - The user notebooks are based on the [Scipy-notebook](https://github.com/jupyter/docker-stacks/tree/main/images/scipy-notebook) image, including common packages for data science and machine learning.
    - The [Jupyterlab-pioneer](https://pypi.org/project/jupyterlab-pioneer/) Extension logs telemetry data from the user's interactions with the notebook.
    - The [Jupyter-chat](https://github.com/jupyterlab/jupyter-chat) Extension is used to integrate a chat interface into the notebook.
    - The `chat_interact.py` script is used to interact with the chatbot server by watching the chat files for changes and sending the messages to the chatbot server. Currently, the chatbot server is running in the host server, but it will be moved to the individual user containers in the future.
- The chatbot server (in `history_app.py`) is a LangChain-based server that provides a REST API for the chatbot. It uses the Ollama server for the LLM. 
    - The chatbot server also uses the FileChatMessageHistory class to process the chat history for each conversation, stored in the `chat_histories` directory.
    - The chatbot server currently runs in the host server (it will be moved to the `jupyterhub` container in the future).
- The Ollama server can be containerized or run in the host server.

## Setup and Configuration
This setup has was developed and tested on Ubuntu 22.04. 

### Prerequisites
- Docker
- Docker Compose
- Python 3.10+

### JupyterHub server
Build and run the JupyterHub server using docker compose. This will create a JupyterHub instance using the latest image from the JupyterHub Docker Hub repo (quay.io/jupyterhub/jupyterhub) with the volume `jupyterhub-data` to persist data for individual users and a network `jupyterhub-network` to allow communication between the JupyterHub server, the individual user servers, and the chatbot server.
- Go to the `jupyterhub-docker` directory
- Run `docker compose build` to build the container
- Run `docker compose up -d` to start the container in detached mode.

### Individual User Servers
The individual user servers are automatically created (or *spawned*) when a user is created in the JupyterHub server. These servers include the necessary configuration for the JupyterLab-Pioneer and Jupyter-Chat extensions to log telemetry data and enable chat functionality in the notebook.

To build the image from the Dockerfile:
- go to the `jupyterhub-docker/user-notebook` directory
- `docker build -t user-notebook .` - this will build the image and tag it as `user-notebook`.


### Chatbot LangChain Server
Currently, the server is not containerized. Python 3.10 or later must be installed in the host server to create the appropriate environment. To run the LangChain server:
- Go to `ds-tutor`
    - `python3 -m venv chatbot`
    - `source chatbot/bin/activate`
    - `pip install -r chatbot_requirements.txt`
- run the app in the host server (in *chatbot* env): `nohup uvicorn history_app:app --workers 16 --port 8002 > applogshist.txt &`
    - The app uses message persistence with files ([server](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/server.py), [client](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/client.ipynb))

### Chatbot File Watcher
Currently, the chatbot is not containerized. Python 3.10 or later must be installed in the host server. To run the chatbot interactively:
- `pip3 install langserve watchdog`
- Run **chat_interact.py** not in *chatbot*, but in host server's base python, since Docker volumes need `sudo` access:  
- `sudo python3 chat_interact.py -chatfile-path  /data/docker/volumes/jupyterhub-user-participant7/_data/EDA.chat`

### Ollama Server
For a local LLM server, you can use [Ollama](https://ollama.com/). Follow the instructions in the [Ollama server documentation](https://github.com/varunvasudeva1/ollama-server-docs?tab=readme-ov-file) to install and run Ollama as a service.
Performance will depend on the host server's capability, we have achieved good performance with basic conversations using Llama 3.1 8b (the smallest model) and 70b_q8 (quantized to 8-bit) and near-real-time response with a Nvidia A40 GPU. 
Ollama can also be run in a container (this has not been tested with the current setup). To run the Ollama server in a container, run the following command:
- `docker run -d -p 11434:11434 ollama/ollama:latest`


### Nginx Reverse Proxy
- To access JupyterHub from outside the local network, follow the official [JupyterHub documentation](https://jupyterhub.readthedocs.io/en/stable/howto/configuration/config-proxy.html#nginx) to set up the Nginx reverse proxy.
- To serve Ollama from outside the local network, you can use the Nginx reverse proxy to forward requests to the Ollama server, see the [Ollama server documentation](https://github.com/ollama/ollama/blob/main/docs/faq.md#how-can-i-use-ollama-with-a-proxy-server) for details.
