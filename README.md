# JELAI: a Jupyter Environment for Learning Analytics and AI
## System Architecture
![ds-tutor architecture](./images/JELAIOctober.jpg)
<a href="https://www.flaticon.com/free-icons/" title="icons" style="font-size: 0.5em;">Icons created by juicy_fish - Flaticon</a>

## Overview
JELAI is a system that integrates a Jupyter environment with a chatbot to provide a learning analytics and AI platform. 
The system is designed to support education using Jupyter notebooks, such as programming, data science and machine learning, by providing a collaborative environment where students can interact with Jupyter notebooks and receive assistance from a chatbot. 
The chatbot uses a large language model (LLM) to provide responses based on the chat history and their actions as they work through the notebooks. 
JELAI is intended to help students learn and explore, get feedback on their work, and receive guidance on problem-solving.
For instructors, the system can provide insights into student interactions with the notebooks, allowing them to monitor progress, identify areas where students may need help, and provide targeted support.
For researchers, the system can be used to collect data on student interactions and explore the use of LLMs in educational settings.

Table of Contents:
- [Description](#description)
- [Setup and Configuration](#setup-and-configuration)
- [Development and Local Experimentation](#development-and-local-experimentation)

### Description
The system consists of a JupyterHub server, individual user Jupyter servers, a chatbot server, and an Ollama server. 
- The JupyterHub server (containerized, running in the `jupyterhub-docker` Docker network) handles user authentication and administration of individual user servers.
- The individual user Jupyter servers are automatically created (or *spawned*) when a user is created in the JupyterHub server (containerized and run in the `jupyterhub-docker` Docker network)
    - The user notebooks are based on the [Scipy-notebook](https://github.com/jupyter/docker-stacks/tree/main/images/scipy-notebook) image, including common packages for data science and machine learning.
    - The [Jupyterlab-pioneer](https://pypi.org/project/jupyterlab-pioneer/) Extension logs telemetry data from the user's interactions with the notebook.
    - The [Jupyter-chat](https://github.com/jupyterlab/jupyter-chat) Extension is used to integrate a chat interface into the notebook.
    - The `chat_interact.py` script is used to interact with the LLM-handler server by watching the chat files for changes and sending the messages to the server.
- The LLM-handler server (in `history_app.py`) is a LangChain-based server that provides a REST API for the chatbot. It works with the Ollama server. 
    - The LLM-handler server also uses the FileChatMessageHistory class to process the chat history for each conversation, stored in the `chat_histories` directory.
    - The LLM-handler server currently runs in the host server (it will be moved to a separate container in the future).
- The Ollama server can run locally in the host machine or on a separate one. Cloud or third-party services can also be used, but the system is designed to work with a self-hosted server. 

## Setup and Configuration
This setup has was developed and tested on Ubuntu 22.04. 

### Prerequisites
- Docker
- Docker Compose
- Python 3.10 or 3.11

### JupyterHub server
Build and run the JupyterHub server using docker compose. This will create a JupyterHub instance using the latest image from the JupyterHub Docker Hub repo (quay.io/jupyterhub/jupyterhub) with the volume **jupyterhub-data** to persist data for individual users and a network **jupyterhub-network** to allow communication between the JupyterHub server, the individual user servers, and the chatbot server.
- Go to the **jupyterhub-docker** directory in the terminal
- Run `docker compose build` to build the container
- Run `docker compose up -d` to start the container in detached mode.

### Individual User Servers
The individual user servers are automatically created (or *spawned*) when a user is created in the JupyterHub server. These servers include the necessary configuration for the JupyterLab-Pioneer and Jupyter-Chat extensions to log telemetry data and enable chat functionality in the notebook.

To build the image from the Dockerfile:
- Go to the **jupyterhub-docker/user-notebook** directory in the terminal
- Run `docker build -t user-notebook .` - this will build the image and tag it as `user-notebook`. If you make any changes to the Dockerfile, such as adding specific packages, you will need to rebuild the image. You can version the image by adding a tag, e.g., `user-notebook:v1` and changing that in the **docker-compose.yml** file in the **jupyterhub-docker** directory.


### LLM-Handler Server
Currently, this server is not containerized so it must be run manually. Python 3.10 or later must be installed in the host server to create the appropriate environment. To run the server:
- Go to the home directory where the repository was cloned:
    - Create a virtual environment: `python3 -m venv chatbot`
    - Activate it: `source chatbot/bin/activate`
    - Install the requirements: `pip install -r chatbot_requirements.txt`
- run the app in the host server (in *chatbot* env): `nohup uvicorn history_app:app --workers 16 --port 8002 --host 0.0.0.0 > applogshist.txt &`
    - The app uses message persistence with files ([server](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/server.py), [client](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/client.ipynb))

### Chatbot File Watcher
The chat interaction app in **chat_interact.py** watches the chat files for changes and sends the messages to the chatbot server. It automatically runs in the individual containers.
Currently, the [Jupyter-chat](https://github.com/jupyterlab/jupyter-chat) extension limits exploration to the JupyterLab [root directory](https://github.com/jupyterlab/jupyter-chat/issues/61), so there is the risk that users could access or modify the chat files. This will be addressed in future versions.

### Ollama Server
For a local LLM server, you can use [Ollama](https://ollama.com/). Follow the instructions in the [Ollama server documentation](https://github.com/varunvasudeva1/ollama-server-docs?tab=readme-ov-file) to install and run Ollama as a service.
Performance will depend on the host server's capability, we have achieved acceptable responses with basic conversations in English using Llama 3.1 8b (the smallest model) and great answers within 15 seconds with the 70b model on an Nvidia A40 GPU. 
Ollama can also be containerized. To run the Ollama server in a container, run the following command:
- `docker run -d -p 11434:11434 ollama/ollama:latest`

Third-party services (cloud LLM providers) have not been evaluated, but in theory, they can be used as long as they provide a REST API for the chatbot server to interact with.
The model within the **history_app.py** file may need to be modified to work with different LLM servers.

### Nginx Reverse Proxy
To access JupyterHub from outside the local network, follow the official [JupyterHub documentation](https://jupyterhub.readthedocs.io/en/stable/howto/configuration/config-proxy.html#nginx) to set up the Nginx reverse proxy. Similarly, to serve Ollama from a separate machine to the one running JELAI, you can use the Nginx reverse proxy to forward requests to Ollama, see the [Ollama server documentation](https://github.com/ollama/ollama/blob/main/docs/faq.md#how-can-i-use-ollama-with-a-proxy-server) for details.


## Development and Local Experimentation
To run the system locally for development and experimentation, you can use JupyterLab and the chatbot server in your local environment.
This does not require Docker, but it needs Python 3.10 or 3.11. 
For the Ollama server, see the steps above.

1. Create a venv and install the necessary packages:
    - `python -m venv chatbot`
    - `source chatbot/bin/activate`, on Windows use `chatbot\Scripts\activate`
    - `python.exe -m pip install -r chatbot_requirements.txt`
2. On a different terminal, create a venv for the interface that will run JupyterLab:
    - `python -m venv jupyterlab`
    - `source jupyterlab/bin/activate`, on Windows use `jupyterlab\Scripts\activate`
    - `python.exe -m pip install -r interface_requirements.txt`
3. Create your environment variables file, where you will add the address of the Ollama server you're using:
    - Create an **.env** file in the **ds-tutor** directory
    - Add the following line to the **.env** file: `base_url=http://localhost:11434` if you have it local or the address of your Ollama server
4. On the first terminal, still running the **chatbot** environment and run the LLM-handler server:
    - `python history_app.py`
    - Type `Ctrl+C` to stop the server. This server must be active to process the chat messages.
5. Open a new terminal, activate the (**chatbot**) environment and run the chatbot handler:
    - `source chatbot/bin/activate` on Windows use `chatbot\Scripts\activate`
    - `python .\jupyterhub-docker\user-notebook\chat_interact.py working-directory` and this will check for any new chats created in the directory provided and send them to the chatbot server.
    - Type `Ctrl+C` to stop the chatbot handler. This script must be active to send the chat messages to the chatbot server.
6. Add the jupyterlab-pioneer [configuration](https://jupyter-server.readthedocs.io/en/latest/operators/configuring-extensions.html) file to the JupyterLab configuration directory:
    - On the terminal with the **jupyterlab** environment, run `jupyter --path`
    - Copy the config file (see the [examples](https://github.com/educational-technology-collective/jupyterlab-pioneer/tree/main/configuration_examples)), named **jupyter_jupyterlab_pioneer_config.py** to the appropriate path. For development, use the **file_exporter** and set the correct path. See the config in **jupyterhub-docker/user-notebook/jupyter_jupyterlab_pioneer_config.py**.
    - You only have to do this once, the configuration will be saved in the JupyterLab configuration directory.
7. On the terminal with the **jupyterlab** environment, run the JupyterLab interface:
    - `jupyter lab`
    - The JupyterLab interface will open in your browser. You can now interact with the chatbot and use the JupyterLab-Pioneer extension to log telemetry data.
8. To run the :construction: experimental :construction: log processing script, activate the **chatbot** environment and run the script:
    - `python process_logs.py path-to-log-file path-to-output-directory`
    - This script will process the logs in the **logs** file (the one configured in step 6 **jupyter_jupyterlab_pioneer_config.py**) and create a JSON file with the processed logs for each notebook in the given directory.
    - For the LLM to see the logs as context, <ins>the notebook and the chat file must have the same name</ins>. 