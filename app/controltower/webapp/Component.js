sap.ui.define(["sap/ui/core/UIComponent", "com/aegis/controltower/model/models"], (UIComponent, models) => {
    "use strict";
    return UIComponent.extend("com.aegis.controltower.Component", {
        metadata: {
            manifest: "json",
            interfaces: ["sap.ui.core.IAsyncContentCreation"]
        },
        init() {
            UIComponent.prototype.init.apply(this, arguments);
            this.setModel(models.createDeviceModel(), "device");
            this.getRouter().initialize();
        }
    });
});
