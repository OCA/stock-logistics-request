import {ProductCatalogKanbanRecord} from "@product/product_catalog/kanban_record";
import {patch} from "@web/core/utils/patch";
import {StockRequestCatalogOrderLine} from "./order_line.esm";

patch(ProductCatalogKanbanRecord.prototype, {
    get orderLineComponent() {
        if (this.env.orderResModel === "stock.request.order") {
            return StockRequestCatalogOrderLine;
        }
        return super.orderLineComponent;
    },
});
