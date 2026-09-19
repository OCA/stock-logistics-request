import {_t} from "@web/core/l10n/translation";
import {ProductCatalogKanbanController} from "@product/product_catalog/kanban_controller";
import {patch} from "@web/core/utils/patch";

patch(ProductCatalogKanbanController.prototype, {
    _defineButtonContent() {
        if (this.orderResModel === "stock.request.order") {
            this.buttonString = _t("Back to Stock Request");
            return;
        }
        super._defineButtonContent();
    },
});
