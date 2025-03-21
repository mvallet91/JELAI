# JELAI: a Jupyter Environment for Learning Analytics and AI
## System Architecture
![ds-tutor architecture](./images/Architecture.jpg)
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
The system consists of a JupyterHub server, individual user Jupyter servers, a middleware server, and an Ollama server. 
- The JupyterHub server (containerized, running in the `jupyterhub-docker` Docker network) handles user authentication and management of individual user servers.
- The **individual user** Jupyter servers are automatically created (or *spawned*) when a user is created in the JupyterHub server (each user has their own container, which is connected to the `jupyterhub-docker` Docker network)
    - The user notebooks are based on the [Scipy-notebook](https://github.com/jupyter/docker-stacks/tree/main/images/scipy-notebook) image, including common packages for data science and machine learning.
    - The [Jupyterlab-pioneer](https://pypi.org/project/jupyterlab-pioneer/) Extension logs telemetry data from the user's interactions with the notebook.
    - The [Jupyter-chat](https://github.com/jupyterlab/jupyter-chat) Extension is used to integrate a chat interface into the notebook.
    - The `chat_interact.py` script in the notebook image is used to interact with the LLM-handler server by watching the chat files for changes and sending the messages to the server.
    - The `process_logs.py` script in the notebook image processes the telemetry logs from the JupyterLab-Pioneer extension to create a JSON file with the processed logs for each notebook.
- The **middleware** container runs the LLM-handler server and the LA module.
    - The LLM-handler server (in `llm_handler.py`) is a LangChain-based server that provides a REST API for the chatbot. It uses the FileChatMessageHistory class to process the chat history for each conversation, stored in the `chat_histories` directory and calls the Ollama server to generate responses.
    - The LA module (in progress) processes the telemetry logs from the JupyterLab-Pioneer to generate insights and visualizations for instructors and researchers, and trigger interventions based on user actions.
- **Fluent** is used to collect logs from the individual containers and send them to the middleware container for storage and processing with the LA module.
- The **Ollama** server can run locally in the host machine or on a separate one. Cloud or third-party services can also be used, but the system is designed to work with a self-hosted server. 

## Setup and Configuration
This setup has was developed and tested on Ubuntu 22.04 and 24.04. 

### Prerequisites
- Docker
- Docker Compose
- Python 3.10 or above

### Quick Start
Build and run the JupyterHub server using docker compose. This will create a JupyterHub instance using the latest image from the JupyterHub Docker Hub repo (quay.io/jupyterhub/jupyterhub) with the volume **jupyterhub-data** to persist data for individual users and a network **jupyterhub-network** to allow communication between the JupyterHub server, the individual user servers, and the chatbot server.
- Clone this repository to your local machine
- Run the Ollama server (see below)
- Create an **.env** file in the **jupyterhub-docker/middleware** directory and add the Ollama server address:
    - `ollama_url=http://localhost:11434` if you have it local, otherwise the address of your Ollama server
- Go to the **jupyterhub-docker** directory in the terminal
- Run `docker compose build` to build the container
- Run `docker compose up -d` to start the container in detached mode.
- Access the JupyterHub server at `http://localhost:8000` in your browser (see *Nginx* below for public access). 
- The default admin user is `admin`, create a new user called admin, with a new password, to access the system.
- To stop the system, run `docker compose down`.

### Pedagogical Configuration
The two basic adjustments to the system are the system prompt for the assistant and the learning objectives for the course and per notebook.
- **System Prompt**: The system prompt for the assistant can be set in the `llm_handler.py` file in the **jupyterhub-docker/middleware** directory.
- **Learning Objectives**: The learning objectives for the course and per notebook can be set in the `learning_objectives.yaml` file in the **jupyterhub-docker/middleware** directory.

### Individual User Servers
The individual user servers are automatically created (or *spawned*) when a user is created in the JupyterHub server. These servers include the necessary configuration for the JupyterLab-Pioneer and Jupyter-Chat extensions to log telemetry data and enable chat functionality in the notebook. The image is built automatically using the Dockerfile in the user-notebook directory.

### User Working Environment
In the Dockerfile in the user-notebook directory, the working directory for the chatbot interaction is set to the **working-directory** environment variable. This is the local directory where students see their notebooks and chat files. 
To add course or experiment materials, the files can be added to the **working-directory** in the user-notebook image.
Additionally, the default directory for chat files can be set in the Dockerfile, for example by setting `{"defaultDirectory": "chats/"}'`.
Check the Dockerfile in the user-notebook directory for more details.

### Chatbot File Watcher
The chat interaction app in **chat_interact.py** watches the chat files for changes and sends the messages to the chatbot server. It automatically runs in the individual containers.
The [Jupyter-chat](https://github.com/jupyterlab/jupyter-chat) extension used to limit exploration to the JupyterLab [root directory](https://github.com/jupyterlab/jupyter-chat/issues/61). 
Now the directory can be specified in the Dockerfile of the user-notebook image, for example by setting ``{"defaultDirectory": "chats/"}'`.

### Ollama Server
For a local LLM server, you can use [Ollama](https://ollama.com/). Follow the instructions in the [Ollama server documentation](https://github.com/varunvasudeva1/ollama-server-docs?tab=readme-ov-file) to install and run Ollama as a service.
Performance will depend on the host server's capability, we have achieved acceptable responses with basic conversations in English using Llama 3.1 8b (the smallest model) and great answers within 15 seconds with the 70b model on an Nvidia A40 GPU. 
Ollama can also be containerized. To run the Ollama server in a container, run the following command:
- `docker run -d -p 11434:11434 ollama/ollama:latest`

Third-party services (cloud LLM providers) have not been evaluated, but in theory, they can be used as long as they provide a REST API for the chatbot server to interact with.

### Nginx Reverse Proxy
To access JupyterHub from outside the local network, follow the official [JupyterHub documentation](https://jupyterhub.readthedocs.io/en/stable/howto/configuration/config-proxy.html#nginx) to set up the Nginx reverse proxy. Similarly, to serve Ollama from a separate machine to the one running JELAI, you can use the Nginx reverse proxy to forward requests to Ollama, see the [Ollama server documentation](https://github.com/ollama/ollama/blob/main/docs/faq.md#how-can-i-use-ollama-with-a-proxy-server) for details.

## FAQ:
- Where can I edit the system prompt for the assistant?
    - The system prompt for the assistant can be set in the `llm_handler.py` file in the `jupyterhub-docker/middleware` directory.
- Can I add notebooks or materials so they are available to all users?
    - Yes, you can add course materials to the **working-directory** in the user-notebook image, using the Dockerfile.
- What if I can't run Ollama locally?
    - You can use a third-party service that provides a REST API for the chatbot server to interact with. The system is designed to work with a self-hosted server, but other services can be used.



## Development and Local Experimentation
To run the system locally for development and experimentation, you can use **JupyterLab** (instead of JupyterHub) and the chatbot server in your local environment.
This does not require Docker, but it needs Python 3.12. 

For the Ollama server, see the steps above.

1. Create a venv and install the necessary packages for the LLM Handler:
    - Navigate to the Middleware directory in the terminal: `cd jupyterhub-docker/middleware`
    - `python -m venv llm-handler`
    - `source llm-handler/bin/activate`, on Windows use `llm-handler\Scripts\activate`
    - `python.exe -m pip install -r requirements.txt`
2. On a different terminal, create a venv for the interface that will run JupyterLab:
    - Stay in the home directory of the repository
    - `python -m venv jupyterlab`
    - `source jupyterlab/bin/activate`, on Windows use `jupyterlab\Scripts\activate`
    - `python.exe -m pip install -r requirements.txt`
3. On a third terminal, create a venv for the chat handler server:
    - Navigate to the user-notebook directory in the terminal: `cd jupyterhub-docker/user-notebook`
    - `python -m venv chatbot`
    - `source chatbot/bin/activate`, on Windows use `chatbot\Scripts\activate`
    - `python.exe -m pip install -r chat_interact_requirements.txt`
4. Create your environment variables file, where you will add the address of the Ollama server you're using (you must setup Ollama before this step, see above):
    - Create an **.env** file in the **jupyterhub-docker/middleware** directory
    - Add the following line to the **.env** file: `ollama_url=http://localhost:11434` if you have it local or the address of your Ollama server
5. On the first terminal, still running the **llm-handler** environment and run the LLM-handler server:
    - `python llm_handler.py`
    - Type `Ctrl+C` to stop the server. This server must be active to process the chat messages.
6. On the terminal running the **chatbot** environment, run the chatbot handler:
    - `python .\jupyterhub-docker\user-notebook\chat_interact.py [working-directory] [processed-logs-directory]` and this will check for any new chats created in the directory provided and send them to the chatbot server. Here, the `working-directory` is where the chats are stored, and `processed-logs` is where you keep the output of the log processing script, see step 9 below.
    - Type `Ctrl+C` to stop the chatbot handler. This script must be active to send the chat messages to the chatbot server.
7. Add the jupyterlab-pioneer [configuration](https://jupyter-server.readthedocs.io/en/latest/operators/configuring-extensions.html) file to the JupyterLab configuration directory:
    - On the terminal with the **jupyterlab** environment, run `jupyter --path`
    - Copy the config file (see the [examples](https://github.com/educational-technology-collective/jupyterlab-pioneer/tree/main/configuration_examples)), named **jupyter_jupyterlab_pioneer_config.py** to the appropriate path. For development, use the **file_exporter** and set the correct path. See the config in **jupyterhub-docker/user-notebook/jupyter_jupyterlab_pioneer_config.py**.
    - You only have to do this once, the configuration will be saved in the JupyterLab configuration directory.
8. On the terminal with the **jupyterlab** environment, run the JupyterLab interface:
    - `jupyter lab`
    - The JupyterLab interface will open in your browser. You can now interact with the chatbot and use the JupyterLab-Pioneer extension to log telemetry data.
    - Close JupyterLab by navigating to **File > Shut Down** in the interface.
9. To run the :construction: experimental :construction: log processing script, activate the **chatbot** environment and run the script:
    - `python process_logs.py path-to-log-file path-to-output-directory`
    - This script will process the logs in the **logs** file (the one configured in step 6 **jupyter_jupyterlab_pioneer_config.py**) and create a JSON file with the processed logs for each notebook in the given directory.
    - For the LLM to see the logs as context, <ins>the notebook and the chat file must have the same name</ins>. 