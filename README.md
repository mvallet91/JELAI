
## JupyterHub Setup
This setup has was developed and tested on Ubuntu 22.04. 

### Prerequisites
- Docker Compose
- Python 3.10+

### JupyterHub server
Clone and run the JupyterHub using docker compose. This will create a JupyterHub server using the latest image from the JupyterHub Docker Hub repo (quay.io/jupyterhub/jupyterhub) with the volume `jupyterhub-data` to persist data for individual users and a network `jupyterhub-network` to allow communication between the JupyterHub server, the individual user servers, and the chatbot server.
- git clone https://github.com/jupyterhub/jupyterhub-deploy-docker.git
- cd basic-example
- docker compose build
- docker compose up -d

### Individual User Servers
- `pip install jupyterlab_collaborative_chat jupyterlab_pioneer pandas seaborn matplotlib numpy`
- Create `logs` folder for user from user server (or assign permission `chown -R username logs`)
- Copy [jupyter_jupyterlab_pioneer_config](https://github.com/educational-technology-collective/jupyterlab-pioneer/blob/main/configuration_examples/file_exporter/jupyter_jupyterlab_pioneer_config.py) (in `/etc/jupyter/`)  e.g. `/data/docker/volumes/jupyterhub-user-participant6/_data/jupyter_jupyterlab_pioneer_config.py` then cp into `/etc/jupyter`

### Nginx Reverse Proxy
Follow the official [JupyterHub documentation](https://jupyterhub.readthedocs.io/en/stable/howto/configuration/config-proxy.html#nginx) to set up the Nginx reverse proxy.


- clone ds-tutor or copy repo to shared volume
    - `python3 -m venv chatbot`
    - `source chatbot/bin/activate`
    - `pip install -r /shared-volume/ds-tutor/chatbot_requirements.txt`
- run **app** in host server (in *chatbot* env): `nohup uvicorn history_app:app --workers 16 --port 8002 > applogshist.txt &`
    - The app uses message persistence with files ([server](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/server.py), [client](https://github.com/langchain-ai/langserve/blob/main/examples/chat_with_persistence/client.ipynb))

- Run **chat_interact.py** (not in *chatbot*, but in host server since Docker volumes need sudo...):  `python chat_interact.py -chatfile-path  /data/docker/volumes/jupyterhub-user-participant7/_data/EDA.chat`