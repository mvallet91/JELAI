# Shutdown the Jupyter server after no activity for 60 minutes
c.ServerApp.shutdown_no_activity_timeout = 3600

# Kill kernels after 30 minutes of inactivity
c.MappingKernelManager.cull_idle_timeout = 1800
c.MappingKernelManager.cull_interval = 1800
c.MappingKernelManager.cull_connected = False

# Disable terminal
c.ServerApp.terminals_enabled = False
