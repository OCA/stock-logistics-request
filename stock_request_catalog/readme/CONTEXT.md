**Business need**

- Building a stock request line by line is slow when many products are
  involved: each product has to be searched and added individually.
- Sale orders already solve this with the *Catalog* view (browse products,
  set quantities, go back to the order). Stock request users want the same.

**Approach**

- Reuse Odoo's `product.catalog.mixin` (the engine behind the sale catalog)
  on `stock.request.order`.

**Useful information**

- Depends on `stock_request` (which pulls in `stock` and `product`).
- Works well alongside `stock_request_product_matrix` for requesting many
  variants of a configurable product at once.
