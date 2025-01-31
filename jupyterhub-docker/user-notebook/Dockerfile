# DS Tutor Notebook Image
# 
# This image is based on the Jupyter Scipy Notebook image and includes additional packages and configurations for DS Tutor.
#
# The image includes the following packages:
# - jupyterlab_collaborative_chat
# - jupyterlab_pioneer
#
# The image also includes a configuration for the JupyterLab Pioneer app to log telemetry data to a file.
# The image is built from the Jupyter Scipy Notebook image.

FROM quay.io/jupyter/scipy-notebook:latest

# Create logs folder
RUN mkdir /home/jovyan/logs && \
    chown -R jovyan:users /home/jovyan/logs

# Copy jupyterlab_pioneer config
COPY jupyter_jupyterlab_pioneer_config.py /etc/jupyter/

# Install additional packages
RUN pip install --no-cache-dir jupyterlab_collaborative_chat jupyterlab_pioneer 

# Switch back to jovyan to avoid running the container as root
USER jovyan

# Set up the work directory
WORKDIR /home/jovyan/work

## Attempt to run the chat_interact.py script in the container
# Create a virtual environment
RUN python -m venv /home/jovyan/venv

# Activate the virtual environment and install requirements
COPY chat_interact_requirements.txt /home/jovyan/
RUN . /home/jovyan/venv/bin/activate && \
   pip install --no-cache-dir -r /home/jovyan/chat_interact_requirements.txt

# Copy the chat_interact.py script
COPY chat_interact.py /home/jovyan/

# TODO Try this with nohup and maybe a log text
# Add the command to run chat_interact.py to the container startup script
CMD ["/bin/bash", "-c", ". /home/jovyan/venv/bin/activate && python /home/jovyan/chat_interact.py /home/jovyan/work > /home/jovyan/chat_interact.log 2>&1 & start-notebook.py"]

# CMD [""]
