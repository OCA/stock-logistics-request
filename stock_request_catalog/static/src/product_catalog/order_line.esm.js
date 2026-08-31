import {ProductCatalogOrderLine} from "@product/product_catalog/order_line/order_line";

export class StockRequestCatalogOrderLine extends ProductCatalogOrderLine {
    get showPrice() {
        return false;
    }
}
