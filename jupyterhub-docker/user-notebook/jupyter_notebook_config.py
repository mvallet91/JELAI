# Shutdown the Jupyter server after no activity for 60 minutes
c.ServerApp.shutdown_no_activity_timeout = 3600

# Kill kernels after 30 minutes of inactivity
c.MappingKernelManager.cull_idle_timeout = 1800
c.MappingKernelManager.cull_interval = 1800
c.MappingKernelManager.cull_connected = False

# Disable terminal
c.ServerApp.terminals_enabled = False

# Max one kernel per user
from jupyter_server.services.kernels.kernelmanager import AsyncMappingKernelManager

class CustomKernelManager(AsyncMappingKernelManager):
    async def start_kernel(self, kernel_id=None, path=None, **kwargs):
        print("CustomKernelManager start_kernel")
        
        # List existing kernels
        kernels = self.list_kernels()

        # Shut down existing kernels before starting a new one
        for kernel in kernels:
            await self.shutdown_kernel(kernel["id"])

        # Start a new kernel (correct method call)
        return await super().start_kernel(kernel_id=kernel_id, path=path, **kwargs)

# Apply the custom kernel manager
c.ServerApp.kernel_manager_class = CustomKernelManager