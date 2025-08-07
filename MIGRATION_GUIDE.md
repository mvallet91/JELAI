# Migration Guide: Implementing YDoc for Chat Files

## Overview

This guide walks through implementing YDoc-based collaborative editing for chat files in the JELAI system. YDoc provides proper collaborative editing capabilities that the current JSON-based approach lacks.

## Current Status (ydoc-integration branch)

The following files have been created/modified on the `ydoc-integration` branch:

### New Files Created:
1. `ydoc_chat_integration.md` - Comprehensive documentation
2. `chat_interact_ydoc.py` - YDoc-based implementation
3. `chat_interact_requirements_ydoc.txt` - Updated requirements
4. `Dockerfile_ydoc_section.txt` - Dockerfile modifications
5. `start_chat_interact.sh` - Script to choose implementation
6. `MIGRATION_GUIDE.md` - This guide

### Key Features of YDoc Implementation:

1. **Collaborative Editing**: Multiple users can edit chat files simultaneously
2. **Conflict Resolution**: Automatic merging of concurrent changes
3. **Atomic Transactions**: All changes are transactional
4. **Real-time Awareness**: See who is currently editing
5. **Fallback Support**: Gracefully falls back to original implementation if YDoc unavailable

## Implementation Steps

### Step 1: Update Requirements

Replace the current requirements file or add YDoc dependencies:

```bash
# Copy the new requirements file
cp chat_interact_requirements_ydoc.txt chat_interact_requirements.txt
```

### Step 2: Update Dockerfile

Replace the current Dockerfile section (lines 69-95) with the content from `Dockerfile_ydoc_section.txt`:

```dockerfile
# Replace the existing section with:
# Create a virtual environment
RUN python -m venv /home/jovyan/venv

# Copy both requirements files
COPY chat_interact_requirements.txt /home/jovyan/
COPY chat_interact_requirements_ydoc.txt /home/jovyan/

# Install basic requirements first
RUN /home/jovyan/venv/bin/pip install --no-cache-dir -r /home/jovyan/chat_interact_requirements.txt

# Try to install YDoc dependencies, but don't fail if they're not available
RUN /home/jovyan/venv/bin/pip install --no-cache-dir -r /home/jovyan/chat_interact_requirements_ydoc.txt || \
    echo "YDoc dependencies not available - will use fallback implementation"

# Copy the chat interaction scripts
COPY chat_interact.py /home/jovyan/
COPY chat_interact_ydoc.py /home/jovyan/
COPY process_logs.py /home/jovyan/
COPY utils.py /home/jovyan/

# Environment variable to choose implementation
ENV USE_YDOC_CHAT=${USE_YDOC_CHAT:-true}

# Get container ID and export it as an environment variable
RUN echo 'export CONTAINER_ID=$(cat /proc/self/cgroup | grep "docker" | sed "s/^.*\///" | tail -n1)' >> /home/jovyan/.bashrc

# Start script that chooses the right chat implementation
COPY start_chat_interact.sh /home/jovyan/
RUN chmod +x /home/jovyan/start_chat_interact.sh

# Updated CMD that uses the start script
CMD ["/bin/bash", "-c", "\
source /home/jovyan/.bashrc && \
/opt/td-agent-bit/bin/td-agent-bit -c /etc/td-agent-bit/td-agent-bit.conf  & \
. /home/jovyan/venv/bin/activate && \
/home/jovyan/start_chat_interact.sh /home/jovyan/work/${CHAT_DIR} /home/jovyan/logs/processed >> /home/jovyan/logs/processed/chat_interact.log 2>&1 & \
. /home/jovyan/venv/bin/activate && \
python /home/jovyan/process_logs.py /home/jovyan/logs/log /home/jovyan/logs/processed >> /home/jovyan/logs/processed/process_logs.log 2>&1 & \
start-notebook.py"]
```

### Step 3: Copy New Files

Copy the new files to the user-notebook directory:

```bash
# Copy the YDoc implementation
cp chat_interact_ydoc.py jupyterhub-docker/user-notebook/

# Copy the requirements file
cp chat_interact_requirements_ydoc.txt jupyterhub-docker/user-notebook/

# Copy the start script
cp start_chat_interact.sh jupyterhub-docker/user-notebook/
```

### Step 4: Update Docker Compose (Optional)

Add environment variable to control YDoc usage in your docker-compose.yml:

```yaml
user-notebook:
  build:
    context: ./user-notebook
    args:
      CHAT_DIR: ${CHAT_DIR:-chats}
  environment:
    - USE_YDOC_CHAT=true  # Set to false to disable YDoc
    - CHAT_DIR=${CHAT_DIR:-chats}
```

### Step 5: Build and Test

```bash
# Build the updated image
docker compose -f docker-compose-dev.yml build user-notebook

# Test the implementation
docker compose -f docker-compose-dev.yml up -d

# Check logs to verify which implementation is being used
docker compose -f docker-compose-dev.yml logs user-notebook
```

## Testing the Implementation

### Test 1: Basic Functionality
1. Start a Jupyter notebook
2. Create a new chat file
3. Send a message
4. Verify Juno responds
5. Check logs for "YDoc dependencies found" message

### Test 2: Collaborative Features
1. Open the same chat file in two browser tabs
2. Send messages from both tabs
3. Verify real-time synchronization
4. Check for conflict resolution

### Test 3: Fallback Behavior
1. Set `USE_YDOC_CHAT=false` in environment
2. Restart container
3. Verify original implementation is used
4. Check logs for "using original implementation" message

## Troubleshooting

### Common Issues:

1. **YDoc dependencies not installing**:
   ```bash
   # Check if packages are available
   pip search jupyterlab-chat
   pip search pycrdt
   ```

2. **Fallback to original implementation**:
   - Check container logs for import errors
   - Verify requirements.txt includes YDoc packages
   - Check if packages installed correctly in venv

3. **Chat files not updating**:
   - Check file permissions
   - Verify watchdog is monitoring correct directory
   - Check for JSON parsing errors in logs

4. **Performance issues**:
   - Monitor memory usage (YDoc keeps documents in memory)
   - Consider implementing document cleanup for inactive chats
   - Check if multiple YDoc instances are running

### Debug Commands:

```bash
# Check if YDoc is available in container
docker exec -it <container> /home/jovyan/venv/bin/python -c "import jupyterlab_chat.ychat; print('YDoc available')"

# Check logs for implementation choice
docker logs <container> | grep -E "(YDoc|fallback|implementation)"

# Monitor chat directory
docker exec -it <container> ls -la /home/jovyan/work/chats/

# Check running processes
docker exec -it <container> ps aux | grep chat_interact
```

## Rollback Plan

If issues occur, you can quickly rollback:

1. **Quick rollback** - Set environment variable:
   ```bash
   export USE_YDOC_CHAT=false
   docker compose restart user-notebook
   ```

2. **Full rollback** - Revert to original Dockerfile:
   ```bash
   git checkout main -- jupyterhub-docker/user-notebook/Dockerfile
   docker compose build user-notebook
   ```

## Benefits After Migration

1. **Collaborative Editing**: Multiple users can edit chat simultaneously
2. **Conflict Resolution**: No more lost messages due to concurrent edits
3. **Real-time Updates**: Changes appear immediately in all connected clients
4. **Better User Experience**: Proper collaborative editing features
5. **Future-Proof**: Aligned with Jupyter ecosystem standards

## Performance Considerations

1. **Memory Usage**: YDoc keeps documents in memory - monitor usage
2. **File System**: Fewer file write operations reduce I/O load
3. **Network**: Efficient delta-based synchronization
4. **Scalability**: Better support for multiple concurrent users

## Next Steps

1. **Monitor Performance**: Track memory usage and response times
2. **Add Metrics**: Implement monitoring for YDoc operations
3. **User Training**: Educate users about collaborative features
4. **Documentation**: Update user documentation with new features
5. **Cleanup**: Remove old implementation files after stable operation

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs for error messages
3. Test with fallback implementation
4. Consult YDoc documentation: https://jupyter-ydoc.readthedocs.io/
5. Check jupyter-chat project: https://github.com/jupyterlab/jupyter-chat
