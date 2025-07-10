# Learning Materials

This directory contains shared datasets, notebooks, and other resources for all users of the JupyterHub environment.

## Usage
- Place any files or folders here that should be available to all users in their JupyterLab environment.
- The default configuration of Juno uses the `chats` directory in the work directory of the user, but this can be changed in the `docker-compose.yml` file, by setting the `CHAT_DIR` environment variable.
- The entire contents of this directory will be copied into the work directory of the user.
- Do **not** place user-specific or sensitive data here.

## Version Control
- This directory is tracked in git. Please do not remove the `.gitkeep` file. 
- The contents of this directory will not be tracked in Version Control, they are only available in this local repository and the user's work directory.