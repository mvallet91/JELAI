
## JupyterHub Setup
This setup has was developed and tested on Ubuntu 22.04. 

### System Architecture
![ds-tutor architecture](./images/DS%20Tutor%20Architecture.png)


### Prerequisites
- Docker Compose
- Python 3.10+

### JupyterHub server
Build and run the JupyterHub server using docker compose. This will create a JupyterHub instance using the latest image from the JupyterHub Docker Hub repo (quay.io/jupyterhub/jupyterhub) with the volume `jupyterhub-data` to persist data for individual users and a network `jupyterhub-network` to allow communication between the JupyterHub server, the individual user servers, and the chatbot server.
- go to `./jupyterhub-docker`
- docker compose build
- docker compose up -d

### Individual User Servers
The individual user servers are automatically created (or *spawned*) when a user is created in the JupyterHub server. Use the following commands to build the image so the container can automatically start when the user server is created.
- go to ./jupyterhub-docker/user-notebook
- docker build -t user-notebook .

### Nginx Reverse Proxy
Follow the official [JupyterHub documentation](https://jupyterhub.readthedocs.io/en/stable/howto/configuration/config-proxy.html#nginx) to set up the Nginx reverse proxy.

Currently, the server is not containerized. Python 3.10 or later must be installed in the host server to create the appropriate environment. To run the LangServer app:
- Go to `ds-tutor`
    - `python3 -m venv chatbot`
    - `source chatbot/bin/activate`
    - `pip install -r chatbot_requirements.txt`
- run the app in the host server (in *chatbot* env): `nohup uvicorn history_app:app --workers 16 --port 8002 > applogshist.txt &`
    - The app uses message persistence with files ([server](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/server.py), [client](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/client.ipynb))


Currently, the chatbot is not containerized. Python 3.10 or later must be installed in the host server. To run the chatbot interactively:
- `pip3 install langserve watchdog`
- Run **chat_interact.py** not in *chatbot*, but in host server's base python, since Docker volumes need `sudo` access:  
- `sudo python3 chat_interact.py -chatfile-path  /data/docker/volumes/jupyterhub-user-participant7/_data/EDA.chat`