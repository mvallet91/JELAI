// JupyterLab extension to hide the Services tab for all users 
define(["@jupyterlab/application", "@jupyterlab/apputils"], function(app, apputils) {
    function hideServicesTab() {
        // Wait for the main area to be ready
        apputils.MainAreaWidgetTracker && setTimeout(function() {
            var tabs = document.querySelectorAll('.jp-SideBar .p-TabBar-tab');
            tabs.forEach(function(tab) {
                if (tab.textContent && tab.textContent.trim().toLowerCase() === 'services') {
                    tab.style.display = 'none';
                }
            });
        }, 1000);
    }
    return {
        id: 'jelai-hide-services-tab',
        autoStart: true,
        activate: function() {
            hideServicesTab();
        }
    };
});
