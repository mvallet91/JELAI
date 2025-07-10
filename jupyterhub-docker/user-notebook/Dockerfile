# DS Tutor Notebook Image
#
# This image is based on the Jupyter Scipy Notebook image and includes additional packages and configurations for DS Tutor.

FROM quay.io/jupyter/datascience-notebook:latest

# Create logs folder
RUN mkdir /home/jovyan/logs && \
    chown -R jovyan:users /home/jovyan/logs
RUN mkdir /home/jovyan/logs/processed && \
    chown -R jovyan:users /home/jovyan/logs/processed

# Copy jupyterlab_pioneer config
COPY jupyter_jupyterlab_pioneer_config.py /etc/jupyter/
# COPY jupyter_server_config.py /etc/jupyter/

# Install additional packages
RUN pip install --no-cache-dir jupyterlab-chat jupyterlab_pioneer folium

# Install Fluent Bit
# Install td-agent-bit
USER root
RUN set -ex && \
    apt-get update && \
    apt-get install -y ca-certificates curl gnupg2 lsb-release apt-utils && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://packages.fluentbit.io/fluentbit.key | gpg --dearmor -o /etc/apt/keyrings/fluentbit.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/fluentbit.gpg] https://packages.fluentbit.io/ubuntu/jammy jammy main" > /etc/apt/sources.list.d/fluent-bit.list && \
    apt-get update && \
    apt-get install -y td-agent-bit && \
    find / -name "td-agent-bit" && \
    /opt/td-agent-bit/bin/td-agent-bit --version && \
    rm -rf /var/lib/apt/lists/*


# Copy td-agent-bit configuration files
COPY fluent-bit.conf /etc/td-agent-bit/td-agent-bit.conf
COPY parsers.conf /etc/td-agent-bit/parsers.conf


# Set permissions
RUN chown root:root /etc/td-agent-bit/td-agent-bit.conf && \
    chown root:root /etc/td-agent-bit/parsers.conf


# Switch back to jovyan to avoid running the container as root
USER jovyan

################# Workspace Configuration #################

# Copy learning materials (shared, version-controlled)
COPY --chown=jovyan:users learning_materials /home/jovyan/work/

# Set up the work directory
WORKDIR /home/jovyan/work

################# Workspace Configuration #################

# Sets the default chat directory as an environment variable, obtained from the docker-compose file
ARG CHAT_DIR=""
ENV CHAT_DIR=${CHAT_DIR}

# Change default chat location 
RUN mkdir -p /home/jovyan/.jupyter/lab/user-settings/jupyterlab-chat-extension && \
   echo '{"defaultDirectory": "'"${CHAT_DIR}"'"}' > /home/jovyan/.jupyter/lab/user-settings/jupyterlab-chat-extension/factory.jupyterlab-settings

# Create a virtual environment
RUN python -m venv /home/jovyan/venv

# Activate the virtual environment and install requirements
COPY chat_interact_requirements.txt /home/jovyan/
RUN /home/jovyan/venv/bin/pip install --no-cache-dir -r /home/jovyan/chat_interact_requirements.txt

# Copy the chat_interact.py script
COPY chat_interact.py /home/jovyan/
COPY process_logs.py /home/jovyan/
COPY utils.py /home/jovyan/

# Get container ID and export it as an environment variable
RUN echo 'export CONTAINER_ID=$(cat /proc/self/cgroup | grep "docker" | sed "s/^.*\///" | tail -n1)' >> /home/jovyan/.bashrc

# Start Fluent Bit, chat_interact.py, and Jupyter Notebook
CMD ["/bin/bash", "-c", "\
source /home/jovyan/.bashrc && \
/opt/td-agent-bit/bin/td-agent-bit -c /etc/td-agent-bit/td-agent-bit.conf  & \
. /home/jovyan/venv/bin/activate && \
python /home/jovyan/chat_interact.py /home/jovyan/work/${CHAT_DIR} /home/jovyan/logs/processed >> /home/jovyan/chat_interact.log 2>&1 & \
. /home/jovyan/venv/bin/activate && \
python /home/jovyan/process_logs.py /home/jovyan/logs/log /home/jovyan/logs/processed >> /home/jovyan/process_logs.log 2>&1 & \
start-notebook.py"]
